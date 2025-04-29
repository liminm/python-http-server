import os
import socket
import threading
import traceback # For more detailed error printing
import argparse

def parse_request(request_bytes):
    """
    Parses the raw HTTP request bytes.

    Args:
        request_bytes: The raw bytes received from the client.

    Returns:
        A dictionary containing parsed request details (method, path, headers),
        or None if parsing fails.
    """
    try:
        request_str = request_bytes.decode('utf-8', errors='replace')
        lines = request_str.split('\r\n')

        # Parse Request Line (e.g., "GET /path HTTP/1.1")
        request_line = lines[0]
        parts = request_line.split(' ')
        if len(parts) < 3:
            print(f"Warning: Malformed request line: {request_line}")
            return None # Indicate parsing failure
        method = parts[0]
        path = parts[1]
        # version = parts[2] # Not strictly needed for current logic, but good to have

        # Parse Headers
        headers = {}
        for line in lines[1:]:
            if line == "": # Empty line signifies end of headers
                break
            if ':' in line:
                key, value = line.split(':', 1)
                headers[key.strip().lower()] = value.strip() # Lowercase keys for consistency

        # Body parsing could be added here if needed (e.g., for POST)

        return {
            "method": method,
            "path": path,
            "headers": headers,
            # "version": version # Optional
        }
    except Exception as e:
        print(f"Error parsing request: {e}")
        traceback.print_exc() # Print detailed traceback
        return None

def route_request(parsed_request):
    """
    Determines the appropriate HTTP response based on the parsed request.

    Args:
        parsed_request: A dictionary containing parsed request details.

    Returns:
        A string containing the full HTTP response.
    """
    if not parsed_request:
        # Handle cases where parsing failed
        return "HTTP/1.1 400 Bad Request\r\n\r\n" # Suggest 400 for bad requests

    method = parsed_request["method"]
    path = parsed_request["path"]
    headers = parsed_request["headers"]

    # --- Routing Logic ---
    if method == "GET":
        if path == "/":
            return "HTTP/1.1 200 OK\r\n\r\n"

        elif path.startswith("/echo/"):
            echo_content = path[len("/echo/"):] # Get the part after /echo/
            return (f"HTTP/1.1 200 OK\r\n"
                    f"Content-Type: text/plain\r\n"
                    f"Content-Length: {len(echo_content)}\r\n"
                    f"\r\n" # End of headers
                    f"{echo_content}")

        elif path == "/user-agent":
            user_agent = headers.get("user-agent", "Unknown") # Safely get header
            return (f"HTTP/1.1 200 OK\r\n"
                    f"Content-Type: text/plain\r\n"
                    f"Content-Length: {len(user_agent)}\r\n"
                    f"\r\n" # End of headers
                    f"{user_agent}")

        elif path.startswith("/files/"):
            # Example: /files/somefile.txt
            file_path = os.curdir + path[len("/files/"):]
            print(f"Path: {path}")
            print(f"File path requested: {file_path}")
            try:
                with open(file_path, 'rb') as f:
                    file_content = f.read()
                return (f"HTTP/1.1 200 OK\r\n"
                        f"Content-Type: application/octet-stream\r\n"
                        f"Content-Length: {len(file_content)}\r\n"
                        f"\r\n" # End of headers
                        f"{file_content.decode('utf-8', errors='replace')}")
            except FileNotFoundError:
                return "HTTP/1.1 404 Not Found\r\n\r\n"

        else:
            # Path not found for GET method
            return "HTTP/1.1 404 Not Found\r\n\r\n"

    else:
        # Handle other methods if needed, otherwise return 404 or 405 Method Not Allowed
        return "HTTP/1.1 404 Not Found\r\n\r\n" # Or potentially 405


def handle_connection(conn, addr):
    """
    Handles an individual client connection: receives, parses, routes, sends.

    Args:
        conn: The client socket object.
        addr: The client address tuple.
    """
    print(f"Connection from {addr}")
    try:
        # 1. Receive Request
        # Increased buffer size slightly, though 1024 is often enough for simple requests
        request_bytes = conn.recv(2048)
        if not request_bytes:
            print(f"Connection from {addr} closed before sending data.")
            return # Exit if no data received

        # 2. Parse Request
        parsed_request = parse_request(request_bytes)
        # Optional: Print parsed details for debugging
        # if parsed_request:
        #     print(f"Parsed Request from {addr}: {parsed_request}")
        # else:
        #     print(f"Failed to parse request from {addr}")


        # 3. Route Request & Generate Response
        response_str = route_request(parsed_request)

        # 4. Send Response
        conn.sendall(response_str.encode('utf-8')) # Use sendall for reliability

    except ConnectionResetError:
        print(f"Connection reset by peer: {addr}")
    except BrokenPipeError:
         print(f"Broken pipe error with client: {addr}")
    except Exception as e:
        print(f"Error handling connection from {addr}: {e}")
        traceback.print_exc() # Print full traceback for debugging
    finally:
        # 5. Close Connection
        try:
            # Optional: Graceful shutdown (may not always be necessary/effective)
            # conn.shutdown(socket.SHUT_WR)
            conn.close()
            print(f"Connection closed with {addr}")
        except Exception as e:
            # Handle potential errors during close if socket is already bad
            print(f"Error closing connection with {addr}: {e}")


def main():
    print("Logs from your program will appear here!")

    url = "localhost"
    port = 4221

    server_socket = None # Initialize to None
    try:
        # Create the server socket
        server_socket = socket.create_server((url, port), reuse_port=True)
        # Set socket options if needed (e.g., server_socket.setsockopt(...))
        print(f"Server listening on {url}:{port}")

        # Main loop to accept connections
        while True:
            # Wait for a new client connection
            client_socket, client_address = server_socket.accept()

            # Create and start a new thread to handle this connection
            # This allows the server to handle multiple clients concurrently
            client_thread = threading.Thread(
                target=handle_connection,
                args=(client_socket, client_address),
                daemon=True # Set as daemon so threads exit when main program exits
            )
            client_thread.start()

    except KeyboardInterrupt:
        print("\nServer interrupted by user (Ctrl+C). Shutting down.")
    except Exception as e:
        print(f"An error occurred in the main server loop: {e}")
        traceback.print_exc()
    finally:
        # Cleanly close the main server socket
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
    directory = args.directory
    if directory:
        print(f"Got directory: {directory}")
        os.chdir(directory)

    main()
