import socket  # noqa: F401


def main():
    # You can use print statements as follows for debugging, they'll be visible when running tests.
    print("Logs from your program will appear here!")

    # Uncomment this to pass the first stage
    #
    server_socket = socket.create_server(("localhost", 4221), reuse_port=True)
    # server_socket.accept()[0].sendall(b"HTTP/1.1 200 OK\r\n\r\n")  # wait for client
    try:
        while True:
            try:
                conn, addr = server_socket.accept()
                print(f"Connection from {addr}")

                req = conn.recv(1024)
                req2 = req.decode()
                reqMsg = req.decode(errors="replace").split(" ")
                reqMethod = reqMsg[0]
                reqPath = reqMsg[1]
                reqVersion = reqMsg[2]
                print(f"{req2=}")
                if req2.startswith("GET / HTTP/1.1"):
                    response = "HTTP/1.1 200 OK\r\n\r\n"
                # elif req2.startswith("GET /echo/") and reqVersion == "HTTP/1.1":
                elif req2.startswith("GET /echo/"):

                    echo_content = reqPath.split("/")[-1]
                    response = f"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 3\r\n\r\n{echo_content}"
                    print(f"{response=}")


                else:
                    response = "HTTP/1.1 404 Not Found\r\n\r\n"
                conn.send(response.encode())
                conn.shutdown(socket.SHUT_WR)
                conn.close()
            except Exception as e:
                print(f"Error handling connection: {e}")
    except KeyboardInterrupt:
        print("\nServer interrupted. Shutting down.")
    finally:
        server_socket.close()


if __name__ == "__main__":
    main()
