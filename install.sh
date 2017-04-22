#!/bin/sh

#TODO replace if condition with test to handle errors using status codes.
env_dir="$HOME/docker_box/db_env" &&
project_dir="$HOME/docker_box" &&
docker_api_port=2375 &&

command_exists(){
    command -v "$@" > /dev/null 2>&1
}


dist_info(){
    lsb_dist='' &&
    dist_version='' &&
    if command_exists lsb_release; then
        lsb_dist="$(lsb_release -si)"
    fi &&
    if [ -z "$lsb_dist" ] && [ -r /etc/lsb-release ]; then
        lsb_dist="$(. /etc/lsb-release && echo "$DISTRIB_ID")"
    fi &&
    if [ -z "$lsb_dist" ] && [ -r /etc/debian_version ]; then
        lsb_dist='debian'
    fi &&
    if [ -z "$lsb_dist" ] && [ -r /etc/fedora-release ]; then
        lsb_dist='fedora'
    fi &&
    if [ -z "$lsb_dist" ] && [ -r /etc/oracle-release ]; then
        lsb_dist='oracleserver'
    fi &&
    if [ -z "$lsb_dist" ] && [ -r /etc/centos-release ]; then
        lsb_dist='centos'
    fi &&
    if [ -z "$lsb_dist" ] && [ -r /etc/redhat-release ]; then
        lsb_dist='redhat'
    fi &&
    if [ -z "$lsb_dist" ] && [ -r /etc/os-release ]; then
        lsb_dist="$(. /etc/os-release && echo "$ID")"
    fi &&
    
    lsb_dist="$(echo "$lsb_dist" | tr '[:upper:]' '[:lower:]')" &&
    
    if [ "${lsb_dist}" = "redhatenterpriseserver" ]; then
            lsb_dist='redhat'
    fi &&
    
    case "$lsb_dist" in
        ubuntu)
            if command_exists lsb_release; then
                dist_version="$(lsb_release --codename | cut -f2)"
            fi &&
            if [ -z "$dist_version" ] && [ -r /etc/lsb-release ]; then
                dist_version="$(. /etc/lsb-release && echo "$DISTRIB_CODENAME")"
            fi
        ;;
    
        debian|raspbian)
            dist_version="$(cat /etc/debian_version | sed 's/\/.*//' | sed 's/\..*//')" &&
            case "$dist_version" in
                8)
                    dist_version="jessie"
                ;;
                7)
                    dist_version="wheezy"
                ;;
            esac
        ;;
    
        oracleserver)
            lsb_dist="oraclelinux" &&
            dist_version="$(rpm -q --whatprovides redhat-release --queryformat "%{VERSION}\n" | sed 's/\/.*//' | sed 's/\..*//' | sed 's/Server*//')"
        ;;
    
        fedora|centos|redhat)
            dist_version="$(rpm -q --whatprovides ${lsb_dist}-release --queryformat "%{VERSION}\n" | sed 's/\/.*//' | sed 's/\..*//' | sed 's/Server*//' | sort | tail -1)"
        ;;
    
        *)
            if command_exists lsb_release; then
                dist_version="$(lsb_release --codename | cut -f2)"
            fi &&
            if [ -z "$dist_version" ] && [ -r /etc/os-release ]; then
                dist_version="$(. /etc/os-release && echo "$VERSION_ID")"
            fi
        ;;
    esac
} &&

create_macvlan_network(){
    echo ' ' &&
    echo '########### Creating MACVLAN network(individual IP adresses)(https://github.com/MicroPyramid/docker-box/wiki/Network) ###########' &&
    printf "Enter Subnet(eg: 88.99.102.64/26): " &&
    read subnet &&
    printf "Enter gateway(eg: 88.99.102.65): " &&
    read gateway &&
    printf "Enter ethernet interface(eg: eth0): " &&
    read ethernet_interface &&
    sudo docker network create -d macvlan -o macvlan_mode=bridge --subnet="$subnet" --gateway="$gateway" -o parent="$ethernet_interface" dbox_macvlan
} &&

create_bridge_network(){
    echo ' ' &&
    echo "########### Creating bridge network(IP's from external subnet)(https://github.com/MicroPyramid/docker-box/wiki/Network) ###########" &&
    printf "Enter Subnet(eg: 88.99.114.16/28): " &&
    read subnet2 &&
    printf "Enter gateway(eg: 88.99.114.17): " &&
    read gateway2 &&
    sudo docker network create --driver=bridge --subnet "$subnet2" --gateway="$gateway2" dbox_bridge &&
    sudo iptables -I DOCKER -d "$subnet2" -j ACCEPT
} &&


#TODO replace 2375 by variable

docker_tcp="[Unit]
Description=Docker HTTP Socket for the API

[Socket]
ListenStream=2375
BindIPv6Only=both
Service=docker.service

[Install]
WantedBy=sockets.target" &&

restrict_api_access(){
    iptables -A INPUT -i lo -p tcp --dport 2375 -j ACCEPT &&
    iptables -A INPUT -p tcp --dport 2375 -j DROP
} &&

install(){
    dist_info &&
    case "$lsb_dist" in
        "Ubuntu"|"ubuntu") sudo apt update -y &&
            sudo apt install -y curl &&
            if ! command_exists docker
            then
                sudo update-grub &&
                curl -sSL https://get.docker.com/ | sh &&
                sudo usermod -aG docker $(whoami)
            fi &&
            sudo apt install -y python3-dev python-pip git python-virtualenv &&
            mkdir "$project_dir" &&
            virtualenv -p python3 "$env_dir" &&
            cd "$project_dir" &&
            . db_env/bin/activate &&
            mkdir docker_box && cd docker_box &&
    
            git init && git remote add origin 'https://github.com/MicroPyramid/docker-box' &&
            git pull origin master &&
            #sed replacement pattern considers ampersand, forward slash and backslash(if seperator)  as special chars.
            secret_key=`python -c 'import random; print("".join([random.SystemRandom().choice("abcdefghijklmnopqrstuvwxyz0123456789!@#$%^*(-_=+)") for i in range(50)]))'`
            sed -i "s/\(SECRET_KEY\s=\s\).*/\1'$secret_key'/g" $project_dir/docker_box/docker_box/settings.py &&
            yes | pip install -r requirements.txt &&
    
            python manage.py migrate &&
            python manage.py createsuperuser &&
    
            if [ "$dist_version" = "xenial" ]
            then
                da_systemd_xenial(){
                    restrict_api_access &&
                    echo "$docker_tcp" > /tmp/docker_tcp.socket &&
                    sudo mv /tmp/docker_tcp.socket /etc/systemd/system/docker_tcp.socket &&
                    sudo systemctl stop docker && sudo systemctl start docker_tcp.socket &&
                    sudo systemctl start docker
                } &&
                curl -Is -X GET http://localhost:"$docker_api_port"/images/json | grep -i 'HTTP/1.1 200 OK' ||
                da_systemd_xenial
            elif [ "$dist_version" = "trusty" ]
            then
                da_upstart(){
                    restrict_api_access &&
                    sudo sed -i 's/DOCKER_OPTS=$/DOCKER_OPTS="-H tcp:\/\/0.0.0.0:'"$docker_api_port"' -H unix:\/\/\/var\/run\/docker.sock"/g' /etc/init/docker.conf &&
                    sudo service docker restart
                } &&
                curl -Is -X GET http://localhost:"$docker_api_port"/images/json | grep -i 'HTTP/1.1 200 OK' ||
                da_upstart
            else
                echo "Can't install for this distribution version" &&
                exit 0
            fi &&
    
            echo ' ' &&
            printf '############## Network Setup(https://github.com/MicroPyramid/docker-box/wiki/Network) #############' &&
            echo ' ' &&
            printf "Are there extra IP's"' with MAC addresses(y/n): ' &&
            read has_mac &&
            if [ "$has_mac" = "y" ]
            then
                create_macvlan_network
            fi &&
            printf "Are there extra IP's"' without MAC addresses(y/n): ' &&
            read has_no_mac &&
            if [ "$has_no_mac" = "y" ]
            then
                create_bridge_network
            fi &&

            echo ' ' &&
            printf "Enter Host IP Address: " &&
            read ip_addr &&
            sed -i "s/\(HOST_IP_ADDR\s=\s\).*/\1'$ip_addr'/g" $project_dir/docker_box/docker_box/settings.py &&
            sed -i "s/\(ALLOWED_HOSTS\s=\s\).*/\1['$ip_addr']/g" $project_dir/docker_box/docker_box/settings.py &&

            printf "Enter a port for docker_box: " &&
            read port &&
            echo "Starting docker_box on port "$port"" &&
            sudo su - $(whoami) -c "cd ${project_dir}/docker_box && . ${env_dir}/bin/activate && python manage.py runserver 0.0.0.0:"$port""
            ;;
    
        "Debian"|"debian")
            sudo apt-get update -y &&
            sudo apt-get install -y curl &&
            if ! command_exists docker
            then
                curl -sSL https://get.docker.com/ | sh &&
                sudo usermod -aG docker $(whoami)
            fi &&
            sudo apt-get install -y python3-dev python-pip git python-virtualenv &&
            mkdir "$project_dir" &&
            virtualenv -p python3 "$env_dir" &&
            cd "$project_dir" &&
            . db_env/bin/activate &&
            mkdir docker_box && cd docker_box &&
    
            git init && git remote add origin 'https://github.com/MicroPyramid/docker-box' &&
            git pull origin master &&
            #sed replacement pattern considers ampersand, forward slash and backslash(if seperator)  as special chars.
            secret_key=`python -c 'import random; print("".join([random.SystemRandom().choice("abcdefghijklmnopqrstuvwxyz0123456789!@#$%^*(-_=+)") for i in range(50)]))'`
            sed -i "s/\(SECRET_KEY\s=\s\).*/\1'$secret_key'/g" $project_dir/docker_box/docker_box/settings.py &&
            yes | pip install -r requirements.txt &&
    
            python manage.py migrate &&
            python manage.py createsuperuser &&
    
            if [ "$dist_version" = "jessie" ]
            then
                da_systemd_jessie(){
                    restrict_api_access &&
                    echo "$docker_tcp" > /tmp/docker_tcp.socket &&
                    sudo mv /tmp/docker_tcp.socket /etc/systemd/system/docker_tcp.socket &&
                    sudo systemctl stop docker && sudo systemctl start docker_tcp.socket &&
                    sudo systemctl start docker
                } &&
                curl -Is -X GET http://localhost:"$docker_api_port"/images/json | grep -i 'HTTP/1.1 200 OK' ||
                da_systemd_jessie
            elif [ "$dist_version" = "wheezy" ]
            then
                docker_api_sysV(){
                    restrict_api_access &&
                    sudo sed -i 's/DOCKER_OPTS=$/DOCKER_OPTS="-H tcp:\/\/0.0.0.0:'"$docker_api_port"' -H unix:\/\/\/var\/run\/docker.sock"/g' /etc/init/docker.conf &&
                    sudo service docker restart
                } &&
                curl -Is -X GET http://localhost:"$docker_api_port"/images/json | grep -i 'HTTP/1.1 200 OK' ||
                docker_api_sysV
            else
                echo "Can't install for this distribution version" &&
                exit 0
            fi &&
    
            create_macvlan_network &&
            create_bridge_network &&
            printf "Enter a port for docker_box: " &&
            read port &&
            echo "Starting docker_box on port "$port"" &&
            sudo su - $(whoami) -c "cd ${project_dir}/docker_box && . ${env_dir}/bin/activate && python manage.py runserver 0.0.0.0:"$port""
            ;;
    
        "CentOS"|"centos")
            sudo yum update -y &&
            sudo yum -y install curl &&
            install_python35(){
                sudo yum -y groupinstall "Development tools" &&
                sudo yum -y install zlib-devel bzip2-devel openssl-devel ncurses-devel sqlite-devel readline-devel tk-devel gdbm-devel db4-devel libpcap-devel xz-devel&&
                curl  https://www.python.org/ftp/python/3.5.2/Python-3.5.2.tgz -o Python-3.5.2.tgz &&
                tar xvfz Python-3.5.2.tgz &&
                cd Python-3.5.2 && ./configure --prefix=/usr/local --enable-shared LDFLAGS="-Wl,-rpath /usr/local/lib" &&
                make && sudo make install
            } &&
            python3 -c 'import sys; assert sys.version_info >= (3,5)' 2> /dev/null ||
            install_python35 &&
            sudo $(which pip3) install virtualenv &&

            if ! command_exists docker
            then
                curl -sSL https://get.docker.com/ | sh &&
                sudo usermod -aG docker $(whoami)
            fi &&

            mkdir "$project_dir" &&
            virtualenv -p python3 "$env_dir" &&
            cd "$project_dir" &&
            . db_env/bin/activate &&
            mkdir docker_box && cd docker_box &&
    
            #if [ "$dist_version" = "6" ]
            #then
            #    sudo yum -y install http://opensource.wandisco.com/centos/6/git/x86_64/wandisco-git-release-6-1.noarch.rpm &&
            #    sudo yum -y install git
            #fi &&
            #TODO update git for centos6
            git init && git remote add origin 'https://github.com/MicroPyramid/docker-box' &&
            git pull origin master &&
            #sed replacement pattern considers ampersand, forward slash and backslash(if seperator)  as special chars.
            secret_key=`python -c 'import random; print("".join([random.SystemRandom().choice("abcdefghijklmnopqrstuvwxyz0123456789!@#$%^*(-_=+)") for i in range(50)]))'`
            sed -i "s/\(SECRET_KEY\s=\s\).*/\1'$secret_key'/g" $project_dir/docker_box/docker_box/settings.py &&
            yes | pip install -r requirements.txt &&

            python manage.py migrate &&
            python manage.py createsuperuser &&
            
            if [ "$dist_version" = "7" ]
            then
                da_systemd_centos(){
                    restrict_api_access &&
                    ls /etc/systemd/system/docker.service.d/ || sudo mkdir /etc/systemd/system/docker.service.d/ &&
                    da_centos_config="[Service]
                    ExecStart=
                    ExecStart=/usr/bin/dockerd -H tcp://127.0.0.1:2375 -H unix://var/run/docker.sock" &&
                    echo "$da_centos_config" > /tmp/docker.conf &&
                    sudo mv /tmp/docker.conf /etc/systemd/system/docker.service.d/ &&
                    sudo systemctl daemon-reload &&
                    sudo systemctl restart docker
                } &&
                curl -Is -X GET http://localhost:"$docker_api_port"/images/json | grep -i 'HTTP/1.1 200 OK' ||
                da_systemd_centos
            elif [ "$dist_version" = "6" ]
            then
                da_sysV(){
                    restrict_api_access &&
                    sudo sed -i 's/DOCKER_OPTS=$/DOCKER_OPTS="-H tcp:\/\/0.0.0.0:'"$docker_api_port"' -H unix:\/\/\/var\/run\/docker.sock"/g' /etc/init/docker.conf &&
                    sudo service docker restart
                } &&
                curl -Is -X GET http://localhost:"$docker_api_port"/images/json | grep -i 'HTTP/1.1 200 OK' ||
                da_sysV
            fi &&

            create_macvlan_network &&
            create_bridge_network &&
            printf "Enter a port for docker_box: " &&
            read port &&
            echo "Starting docker_box on port "$port"" &&
            sudo su - $(whoami) -c "cd ${project_dir}/docker_box && . ${env_dir}/bin/activate && python manage.py runserver 0.0.0.0:"$port""
            ;;
    esac
}

install
