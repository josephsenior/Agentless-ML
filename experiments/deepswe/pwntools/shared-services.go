// Explicit offline protocol diagnostic. HTTP parsing and TLS use Go's stdlib.
package main

import (
    "crypto/sha256"
    "crypto/tls"
    "encoding/hex"
    "encoding/json"
    "flag"
    "fmt"
    "log"
    "net"
    "net/http"
    "os"
    "path/filepath"
    "strings"
    "time"
)

type snapshot struct {
    File string `json:"file"`
    Bytes int `json:"bytes"`
    SHA256 string `json:"sha256"`
}

func load(root string) (map[string][]byte, error) {
    raw, err := os.ReadFile(filepath.Join(root, "manifest.json"))
    if err != nil { return nil, err }
    var manifest struct { Snapshots []snapshot `json:"snapshots"` }
    if err = json.Unmarshal(raw, &manifest); err != nil { return nil, err }
    if len(manifest.Snapshots) != 2 { return nil, fmt.Errorf("unexpected snapshot inventory") }
    bodies := make(map[string][]byte)
    for _, pin := range manifest.Snapshots {
        if pin.File != "pypi.json" && pin.File != "robots.txt" { return nil, fmt.Errorf("unexpected snapshot file") }
        if _, exists := bodies[pin.File]; exists { return nil, fmt.Errorf("duplicate snapshot file") }
        data, err := os.ReadFile(filepath.Join(root, pin.File))
        if err != nil { return nil, err }
        digest := sha256.Sum256(data)
        if len(data) != pin.Bytes || hex.EncodeToString(digest[:]) != pin.SHA256 {
            return nil, fmt.Errorf("snapshot mismatch: %s", pin.File)
        }
        bodies[pin.File] = data
    }
    var versions struct { Versions []string `json:"versions"` }
    if err = json.Unmarshal(bodies["pypi.json"], &versions); err != nil { return nil, err }
    if len(versions.Versions) == 0 { return nil, fmt.Errorf("empty public version list") }
    return bodies, nil
}

func main() {
    root := flag.String("data", "/opt/pwntools-services", "verified snapshot directory")
    certPath := flag.String("cert", "", "ephemeral diagnostic certificate")
    keyPath := flag.String("key", "", "ephemeral diagnostic private key")
    check := flag.Bool("check-data", false, "verify data without starting listeners")
    flag.Parse()
    bodies, err := load(*root)
    if err != nil { log.Fatal(err) }
    if *check { fmt.Println("snapshot verification passed"); return }
    cert, err := tls.LoadX509KeyPair(*certPath, *keyPath)
    if err != nil { log.Fatal(err) }
    plain, err := net.Listen("tcp", "127.0.0.1:80")
    if err != nil { log.Fatal(err) }
    secure, err := net.Listen("tcp", "127.0.0.1:443")
    if err != nil { log.Fatal(err) }
    handler := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        host := strings.ToLower(strings.Split(r.Host, ":")[0])
        code, filename, contentType := http.StatusNotFound, "", ""
        if r.TLS != nil && r.Method == http.MethodGet {
            switch {
            case host == "pypi.org" && r.URL.RequestURI() == "/simple/pwntools/":
                code = http.StatusNotAcceptable
                if strings.Contains(r.Header.Get("Accept"), "application/vnd.pypi.simple.v1+json") {
                    code, filename, contentType = http.StatusOK, "pypi.json", "application/vnd.pypi.simple.v1+json"
                }
            case host == "httpbingo.org" && r.URL.RequestURI() == "/robots.txt":
                code, filename, contentType = http.StatusOK, "robots.txt", "text/plain; charset=utf-8"
            }
        }
        if code == http.StatusOK {
            w.Header().Set("Content-Type", contentType)
            w.Header().Set("Content-Length", fmt.Sprint(len(bodies[filename])))
            w.WriteHeader(code)
            _, _ = w.Write(bodies[filename])
        } else {
            // Google is a protocol fixture, not a copied Google page. Valid
            // unknown requests fail; malformed requests fail in net/http
            // before this handler, producing its real HTTP 400 response.
            http.Error(w, http.StatusText(code), code)
        }
        record, _ := json.Marshal(map[string]any{"host": host, "path": r.URL.RequestURI(),
            "method": r.Method, "status": code, "snapshot": filename, "tls": r.TLS != nil})
        fmt.Println(string(record))
    })
    server := func() *http.Server {
        return &http.Server{Handler: handler, ReadHeaderTimeout: 5*time.Second, IdleTimeout: 5*time.Second}
    }
    go func() { log.Fatal(server().Serve(plain)) }()
    fmt.Println(`{"condition":"offline protocol-service diagnostic - modified environment","listeners":["127.0.0.1:80","127.0.0.1:443"]}`)
    log.Fatal(server().Serve(tls.NewListener(secure, &tls.Config{
        Certificates: []tls.Certificate{cert}, MinVersion: tls.VersionTLS12,
    })))
}
