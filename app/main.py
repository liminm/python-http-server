import argparse
import gzip
import io
import os
import pathlib
import socket
import threading
import traceback  # For more detailed error printing


def parse_request(request_bytes):
    """
    Parses the raw HTTP request bytes.
    """
    try:
        request_str = request_bytes.decode('utf-8', errors='replace')
        lines = request_str.split('\r\n')

        # Extract request line and split into parts
        request_line = lines[0]
        parts = request_line.split(' ')
        if len(parts) < 3:
            print(f"Warning: Malformed request line: {request_line}")
            return None
        method = parts[0]
        path = parts[1]

        # Parse headers into a lowercase-key dict
        headers = {}
        for line in lines[1:]:
            if line == "":
                break
            if ':' in line:
                key, value = line.split(':', 1)
                headers[key.strip().lower()] = value.strip()

        # Determine content length and extract body if present
        content_length = int(headers.get("content-length", 0))
        if content_length > 0:
            body_start = request_str.find('\r\n\r\n') + 4
            body = request_str[body_start:body_start + content_length]
        else:
            body = None

        print(f"Parsed Request: {method} {path} Headers: {headers} Body: {body}")

        return {
            "method": method,
            "path": path,
            "headers": headers,
            "body": body,
        }
    except Exception as e:
        print(f"Error parsing request: {e}")
        traceback.print_exc()
        return None


def route_request(parsed_request):
    """
    Determines the HTTP response based on parsed request.

    Returns (resp_headers_bytes, body_bytes, should_close_flag).
    """
    # Return 400 Bad Request on parse failure
    if not parsed_request:
        resp = "HTTP/1.1 400 Bad Request\r\n\r\n".encode('utf-8')
        return resp, b"", False

    method = parsed_request["method"]
    path = parsed_request["path"]
    headers = parsed_request["headers"]

    # Check for Connection: close request header
    connection_hdr = headers.get("connection", "").lower()
    should_close = "close" in connection_hdr

    # Handle GET /
    if method == "GET" and path == "/":
        # Build response lines
        resp_lines = [
            "HTTP/1.1 200 OK",
        ]
        # Include Connection: close if requested
        if should_close:
            resp_lines.append("Connection: close")
        resp_headers = ("\r\n".join(resp_lines) + "\r\n\r\n").encode('utf-8')
        return resp_headers, b"", should_close

    # Handle GET /echo/...
    if method == "GET" and path.startswith("/echo/"):
        echo_text = path[len("/echo/"):]
        accept_encoding = headers.get("accept-encoding", "")

        # Gzip compression if supported
        if "gzip" in accept_encoding:
            buf = io.BytesIO()
            with gzip.GzipFile(fileobj=buf, mode='wb', mtime=0) as gz:
                gz.write(echo_text.encode('utf-8'))
            body = buf.getvalue()

            resp_lines = [
                "HTTP/1.1 200 OK",
                "Content-Type: text/plain",
                f"Content-Length: {len(body)}",
            ]
            if should_close:
                resp_lines.append("Connection: close")
            resp_headers = ("\r\n".join(resp_lines) + "\r\n\r\n").encode('utf-8')
            return resp_headers, body, should_close

        # Plain text echo
        body = echo_text.encode('utf-8')
        resp_lines = [
            "HTTP/1.1 200 OK",
            "Content-Type: text/plain",
            f"Content-Length: {len(body)}",
        ]
        if should_close:
            resp_lines.append("Connection: close")
        resp_headers = ("\r\n".join(resp_lines) + "\r\n\r\n").encode('utf-8')
        return resp_headers, body, should_close

    # Handle GET /user-agent
    if method == "GET" and path == "/user-agent":
        ua = headers.get("user-agent", "Unknown")
        body = ua.encode('utf-8')

        resp_lines = [
            "HTTP/1.1 200 OK",
            "Content-Type: text/plain",
            f"Content-Length: {len(body)}",
        ]
        if should_close:
            resp_lines.append("Connection: close")
        resp_headers = ("\r\n".join(resp_lines) + "\r\n\r\n").encode('utf-8')
        return resp_headers, body, should_close

    # Handle GET /files/...
    if method == "GET" and path.startswith("/files/"):
        file_path = pathlib.Path(os.curdir, path[len("/files/"):])
        try:
            with open(file_path, 'rb') as f:
                data = f.read()
            accept_encoding = headers.get("accept-encoding", "")
            if "gzip" in accept_encoding:
                buf = io.BytesIO()
                with gzip.GzipFile(fileobj=buf, mode='wb', mtime=0) as gz:
                    gz.write(data)
                data = buf.getvalue()
                content_encoding = "gzip"
            else:
                content_encoding = None

            resp_lines = [
                "HTTP/1.1 200 OK",
                "Content-Type: application/octet-stream",
                f"Content-Length: {len(data)}",
            ]
            if content_encoding:
                resp_lines.insert(2, f"Content-Encoding: {content_encoding}")
            if should_close:
                resp_lines.append("Connection: close")
            resp_headers = ("\r\n".join(resp_lines) + "\r\n\r\n").encode('utf-8')
            return resp_headers, data, should_close
        except FileNotFoundError:
            resp = "HTTP/1.1 404 Not Found\r\n\r\n".encode('utf-8')
            return resp, b"", should_close

    # Handle POST /files/...
    if method == "POST" and path.startswith("/files/"):
        filename = path[len("/files/"):]
        with open(filename, "ab") as f:
            f.write(parsed_request["body"] or b"")
        resp = "HTTP/1.1 201 Created\r\n\r\n".encode('utf-8')
        return resp, b"", should_close

    # Fallback for other methods or paths
    resp = "HTTP/1.1 405 Method Not Allowed\r\n\r\n".encode('utf-8')
    return resp, b"", should_close


def handle_connection(conn, addr):
    """
    Manages the client connection, sending responses and handling closure.
    """
    print(f"Connection from {addr}")
    try:
        while True:
            data = conn.recv(4096)
            if not data:
                break
            parsed = parse_request(data)

            # Route request and get close flag
            resp_headers, body, should_close = route_request(parsed)

            conn.sendall(resp_headers)
            conn.sendall(body)

            # Close if requested
            if should_close:
                break
    except ConnectionResetError:
        print(f"Connection reset by peer: {addr}")
    except BrokenPipeError:
        print(f"Broken pipe error with client: {addr}")
    except Exception as e:
        print(f"Error handling connection from {addr}: {e}")
        traceback.print_exc()
    finally:
        conn.close()
        print(f"Connection closed with {addr}")


def main():
    print("Logs from your program will appear here!")

    url, port = "localhost", 4221
    server_socket = None
    try:
        server_socket = socket.create_server((url, port), reuse_port=True)
        print(f"Server listening on {url}:{port}")
        while True:
            client_socket, client_address = server_socket.accept()
            client_thread = threading.Thread(
                target=handle_connection,
                args=(client_socket, client_address),
                daemon=True
            )
            client_thread.start()
    except KeyboardInterrupt:
        print("\nServer interrupted by user. Shutting down.")
    except Exception as e:
        print(f"Server loop error: {e}")
        traceback.print_exc()
    finally:
        if server_socket:
            print("Closing server socket.")
            server_socket.close()
        print("Server shut down complete.")


def parse_arguments():
    parser = argparse.ArgumentParser(description="An http server for learning")
    parser.add_argument("--directory", help="Specify directory path", required=False)
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_arguments()
    if args.directory:
        print(f"Got directory: {args.directory}")
        os.chdir(args.directory)
    main()
