package main

import (
	"bytes"
	"encoding/json"
	"flag"
    "os"
	"fmt"
	"io"
	"io/ioutil"
	"net"
	"net/http"
	"net/http/httputil"
	"time"

	"./go-spew/spew"
	"./net/websocket"
    "regexp"
    "os/exec"
)


var go_server_port = os.Args[1]
var host_ip_addr = os.Args[2]
var host_port = os.Args[3]
var container_id = os.Args[4]

var port = flag.String("port", go_server_port, "Port for server")
var host = flag.String("host", host_ip_addr+":"+host_port, "Docker host")

var sid_regex = regexp.MustCompile(`.*sessionid=(.*?)\n.*`)

func main() {
	flag.Parse()
	http.Handle("/exec/", mid(websocket.Handler(ExecContainer)))
	http.Handle("/", http.FileServer(http.Dir("./")))
	if err := http.ListenAndServe(":"+*port, nil); err != nil {
		panic(err)
	}
}

func mid(next websocket.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        requestDump, err := httputil.DumpRequest(r, true)
        if err != nil {
            fmt.Println(err)
        }
        sid_find := sid_regex.FindStringSubmatch(string(requestDump))
        sid := sid_find[1]
        auth_out, auth_err := exec.Command("python", "manage.py",  "ncp", container_id, sid).Output()
        if auth_err != nil {
            fmt.Printf("%s", auth_err)
            os.Exit(3)
        }
        fmt.Printf("%s", auth_out)
        next.ServeHTTP(w, r)
    })
}

func ExecContainer(ws *websocket.Conn) {
	container := ws.Request().URL.Path[len("/exec/"):]
	if container == "" {
		ws.Write([]byte("Container does not exist"))
		return
	}
	type stuff struct {
		Id string
	}
	var s stuff
	params := bytes.NewBufferString("{\"AttachStdin\":true,\"AttachStdout\":true,\"AttachStderr\":true,\"Tty\":true,\"Cmd\":[\"/bin/bash\"]}")
	resp, err := http.Post("http://"+*host+"/containers/"+container+"/exec", "application/json", params)
	if err != nil {
		panic(err)
	}
	data, err := ioutil.ReadAll(resp.Body)
	if err != nil {
		panic(err)
	}
	json.Unmarshal([]byte(data), &s)
	if err := hijack(*host, "POST", "/exec/"+s.Id+"/start", true, ws, ws, ws, nil, nil); err != nil {
		panic(err)
	}
	fmt.Println(ws)
	spew.Dump(ws)
}

func hijack(addr, method, path string, setRawTerminal bool, in io.ReadCloser, stdout, stderr io.Writer, started chan io.Closer, data interface{}) error {

	params := bytes.NewBufferString("{\"Detach\": false, \"Tty\": true}")
	req, err := http.NewRequest(method, path, params)
	if err != nil {
		return err
	}
	req.Header.Set("User-Agent", "Docker-Client")
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Connection", "Upgrade")
	req.Header.Set("Upgrade", "tcp")
	req.Host = addr

	dial, err := net.Dial("tcp", addr)
	if tcpConn, ok := dial.(*net.TCPConn); ok {
		tcpConn.SetKeepAlive(true)
		tcpConn.SetKeepAlivePeriod(30 * time.Second)
	}
	if err != nil {
		return err
	}
	clientconn := httputil.NewClientConn(dial, nil)
    defer os.Exit(0)
	defer clientconn.Close()

	clientconn.Do(req)

	rwc, br := clientconn.Hijack()
	defer rwc.Close()

	if started != nil {
		started <- rwc
	}

	var receiveStdout chan error

	if stdout != nil || stderr != nil {
		go func() (err error) {
			if setRawTerminal && stdout != nil {
				_, err = io.Copy(stdout, br)
			}
			return err
		}()
	}

	go func() error {
		if in != nil {
			io.Copy(rwc, in)
		}

		if conn, ok := rwc.(interface {
			CloseWrite() error
		}); ok {
			if err := conn.CloseWrite(); err != nil {
                os.Exit(0)
			}
		}
		return nil
	}()

	if stdout != nil || stderr != nil {
		if err := <-receiveStdout; err != nil {
			return err
		}
	}
	spew.Dump(br)
	go func() {
		for {
			fmt.Println(br)
			spew.Dump(br)
		}
	}()

	return nil
}
