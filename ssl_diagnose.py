"""
ssl_diagnose.py
─────────────────────────────────────────────────────────────────────────────
Run this BEFORE the scraper to figure out exactly why SSL verification is
failing. It prints diagnostic info — paste the full output back for help.

Usage:
    python ssl_diagnose.py
"""

import socket
import ssl
import sys

HOST = "www.cusat.ac.in"
PORT = 443


def section(title):
    print(f"\n{'='*70}\n{title}\n{'='*70}")


section("1. Python & certifi versions")
print(f"Python version : {sys.version}")
try:
    import certifi
    print(f"certifi version: {certifi.__version__}")
    print(f"certifi CA path: {certifi.where()}")
except ImportError:
    print("certifi: NOT INSTALLED")

section("2. Can we resolve the hostname?")
try:
    ip = socket.gethostbyname(HOST)
    print(f"Resolved {HOST} -> {ip}")
except Exception as e:
    print(f"DNS resolution FAILED: {e}")

section("3. Raw TLS handshake — what certificate does the server present?")
try:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE  # just to LOOK at the cert, not validate
    with socket.create_connection((HOST, PORT), timeout=10) as sock:
        with ctx.wrap_socket(sock, server_hostname=HOST) as ssock:
            cert_bin = ssock.getpeercert(binary_form=True)
            cert = ssock.getpeercert()
            print(f"TLS version negotiated : {ssock.version()}")
            print(f"Cipher                 : {ssock.cipher()}")
            print(f"Certificate (no validation) retrieved: {len(cert_bin)} bytes")

    # Decode subject/issuer using cryptography if available, else openssl-style
    try:
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend
        x = x509.load_der_x509_certificate(cert_bin, default_backend())
        print(f"\nSubject : {x.subject.rfc4514_string()}")
        print(f"Issuer  : {x.issuer.rfc4514_string()}")
        print(f"Valid from : {x.not_valid_before_utc}")
        print(f"Valid to   : {x.not_valid_after_utc}")
    except ImportError:
        print("\n(install 'cryptography' package for subject/issuer details:")
        print(" pip install cryptography )")

except Exception as e:
    print(f"Raw TLS handshake FAILED: {e}")

section("4. Does verification succeed using certifi's CA bundle?")
try:
    import certifi
    ctx2 = ssl.create_default_context(cafile=certifi.where())
    with socket.create_connection((HOST, PORT), timeout=10) as sock:
        with ctx2.wrap_socket(sock, server_hostname=HOST) as ssock:
            print("SUCCESS — certifi bundle verifies this server's certificate.")
except Exception as e:
    print(f"FAILED with certifi bundle: {e}")
    print(
        "\nThis strongly suggests something BETWEEN your machine and CUSAT "
        "is intercepting/re-signing HTTPS traffic — typically:\n"
        "  - School/work network proxy or firewall (TLS inspection)\n"
        "  - Antivirus with 'HTTPS scanning' enabled (Kaspersky, Avast, "
        "ESET, Norton, etc. often do this by default)\n"
        "  - A VPN client doing the same\n"
    )

section("5. Does verification succeed using the OS trust store?")
try:
    ctx3 = ssl.create_default_context()  # uses OS default
    with socket.create_connection((HOST, PORT), timeout=10) as sock:
        with ctx3.wrap_socket(sock, server_hostname=HOST) as ssock:
            print("SUCCESS — OS trust store verifies this server's certificate.")
except Exception as e:
    print(f"FAILED with OS trust store: {e}")

print(f"\n{'='*70}")
print("Copy everything above and send it back for diagnosis.")
print(f"{'='*70}")
