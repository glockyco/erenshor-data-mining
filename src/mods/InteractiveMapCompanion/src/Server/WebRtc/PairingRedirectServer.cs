using System.Net;
using System.Net.Sockets;
using System.Text;

namespace InteractiveMapCompanion.Server.WebRtc;

/// <summary>
/// Answers plain HTTP on the sharing port with a redirect to the pairing link, so typing
/// the PC's address into a browser pairs that device. The link names the address the
/// request arrived at, which the browser has just shown it can reach.
/// </summary>
internal sealed class PairingRedirectServer : IDisposable
{
    private const int MaxRequestBytes = 8192;
    private const int TimeoutMs = 5000;

    private readonly Func<IPAddress, string> _linkFor;
    private readonly Action<string> _log;
    private TcpListener? _listener;
    private volatile bool _running;

    public PairingRedirectServer(Func<IPAddress, string> linkFor, Action<string> log)
    {
        _linkFor = linkFor;
        _log = log;
    }

    /// <summary>
    /// The bound TCP port, which differs from the requested one only when that was 0.
    /// </summary>
    public int Port => ((IPEndPoint)_listener!.LocalEndpoint).Port;

    /// <summary>
    /// Binds the TCP port. Throws <see cref="SocketException"/> when it is taken.
    /// </summary>
    public void Start(int port)
    {
        if (_running)
            return;

        var listener = new TcpListener(IPAddress.Any, port);
        listener.Start();
        _listener = listener;
        _running = true;
        new Thread(() => AcceptLoop(listener))
        {
            IsBackground = true,
            Name = "Pairing redirect",
        }.Start();
    }

    public void Stop()
    {
        _running = false;
        _listener?.Stop();
    }

    public void Dispose() => Stop();

    private void AcceptLoop(TcpListener listener)
    {
        while (_running)
        {
            TcpClient client;
            try
            {
                client = listener.AcceptTcpClient();
            }
            catch (SocketException)
            {
                if (!_running)
                    break;
                continue;
            }
            catch (ObjectDisposedException)
            {
                break;
            }

            ThreadPool.QueueUserWorkItem(_ => Serve(client));
        }
    }

    private void Serve(TcpClient client)
    {
        try
        {
            using (client)
            {
                client.ReceiveTimeout = TimeoutMs;
                client.SendTimeout = TimeoutMs;
                var stream = client.GetStream();
                string? requestLine = ReadRequestLine(stream);
                if (requestLine == null)
                    return;

                var local = ((IPEndPoint)client.Client.LocalEndPoint!).Address;
                byte[] response = Encoding.ASCII.GetBytes(Respond(requestLine, local));
                stream.Write(response, 0, response.Length);
                stream.Flush();
            }
        }
        catch (Exception ex)
            when (ex is IOException || ex is SocketException || ex is ObjectDisposedException)
        {
            _log($"Pairing page request failed: {ex.Message}");
        }
    }

    private string Respond(string requestLine, IPAddress local)
    {
        string[] parts = requestLine.Split(' ');
        if (parts.Length < 3 || (parts[0] != "GET" && parts[0] != "HEAD"))
            return Status("405 Method Not Allowed", "Allow: GET, HEAD\r\n");

        string path = parts[1];
        int query = path.IndexOf('?');
        if (query >= 0)
            path = path.Substring(0, query);
        if (path != "/")
            return Status("404 Not Found", "");

        // The link carries the pairing secrets, so no cache may keep it after they rotate.
        return Status("302 Found", $"Location: {_linkFor(local)}\r\nCache-Control: no-store\r\n");
    }

    private static string Status(string status, string headers) =>
        $"HTTP/1.1 {status}\r\n{headers}Content-Length: 0\r\nConnection: close\r\n\r\n";

    /// <summary>
    /// Reads the whole request head and returns its first line, or null when the client
    /// sent nothing usable. Unread request bytes would make closing the socket send a
    /// reset, which can discard the response before the browser reads it.
    /// </summary>
    private static string? ReadRequestLine(NetworkStream stream)
    {
        var head = new byte[MaxRequestBytes];
        int length = 0;
        while (length < head.Length)
        {
            int read = stream.Read(head, length, head.Length - length);
            if (read == 0)
                break;
            int scanFrom = Math.Max(0, length - 3);
            length += read;
            if (ContainsHeadEnd(head, scanFrom, length))
                break;
        }

        string text = Encoding.ASCII.GetString(head, 0, length);
        int lineEnd = text.IndexOf("\r\n", StringComparison.Ordinal);
        return lineEnd > 0 ? text.Substring(0, lineEnd) : null;
    }

    private static bool ContainsHeadEnd(byte[] buffer, int from, int length)
    {
        for (int i = from; i + 3 < length; i++)
        {
            if (
                buffer[i] == '\r'
                && buffer[i + 1] == '\n'
                && buffer[i + 2] == '\r'
                && buffer[i + 3] == '\n'
            )
                return true;
        }
        return false;
    }
}
