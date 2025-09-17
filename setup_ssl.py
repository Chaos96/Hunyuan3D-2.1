#!/usr/bin/env python3
"""
SSL Certificate Setup Tool for Hunyuan3D
Supports multiple certificate sources: Let's Encrypt, self-signed, or custom certificates
"""

import os
import sys
import argparse
import subprocess
import shutil
from pathlib import Path

def check_dependencies():
    """Check if required packages are installed"""
    try:
        import cryptography
        return True
    except ImportError:
        print("📦 Installing cryptography package...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "cryptography"])
            return True
        except subprocess.CalledProcessError:
            print("❌ Failed to install cryptography. Please install manually:")
            print("   pip install cryptography")
            return False

def generate_self_signed_cert(domain="localhost", cert_dir="./certs"):
    """Generate self-signed certificate"""
    print(f"🔐 Generating self-signed SSL certificate for {domain}...")

    if not check_dependencies():
        return False

    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    import datetime

    cert_dir = Path(cert_dir)
    cert_dir.mkdir(exist_ok=True)

    cert_file = cert_dir / 'cert.pem'
    key_file = cert_dir / 'key.pem'

    # Generate private key
    print("  🔑 Generating private key...")
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    # Create certificate
    print("  📜 Creating certificate...")
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "CA"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, "San Francisco"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Hunyuan3D Local"),
        x509.NameAttribute(NameOID.COMMON_NAME, domain),
    ])

    # Add subject alternative names for common localhost variants
    san_list = [
        x509.DNSName("localhost"),
        x509.DNSName("127.0.0.1"),
        x509.DNSName("0.0.0.0"),
        x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
        x509.IPAddress(ipaddress.IPv4Address("0.0.0.0")),
    ]

    if domain not in ["localhost", "127.0.0.1", "0.0.0.0"]:
        san_list.append(x509.DNSName(domain))

    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.datetime.utcnow()
    ).not_valid_after(
        datetime.datetime.utcnow() + datetime.timedelta(days=365)
    ).add_extension(
        x509.SubjectAlternativeName(san_list),
        critical=False,
    ).add_extension(
        x509.BasicConstraints(ca=False, path_length=None),
        critical=True,
    ).add_extension(
        x509.KeyUsage(
            digital_signature=True,
            key_encipherment=True,
            content_commitment=False,
            data_encipherment=False,
            key_agreement=False,
            key_cert_sign=False,
            crl_sign=False,
            encipher_only=False,
            decipher_only=False,
        ),
        critical=True,
    ).sign(key, hashes.SHA256())

    # Write certificate and key
    print("  💾 Saving certificate files...")
    with open(cert_file, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    with open(key_file, "wb") as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ))

    print(f"✅ Certificate generated successfully!")
    print(f"   📄 Certificate: {cert_file}")
    print(f"   🔑 Private key: {key_file}")
    print(f"   🗓️  Valid until: {datetime.datetime.utcnow() + datetime.timedelta(days=365)}")

    return True

def setup_letsencrypt(domain, email, cert_dir="./certs"):
    """Setup Let's Encrypt certificate using certbot"""
    print(f"🌐 Setting up Let's Encrypt certificate for {domain}...")

    # Check if certbot is available
    if not shutil.which("certbot"):
        print("📦 Installing certbot...")
        try:
            # Try different package managers
            if shutil.which("apt-get"):
                subprocess.check_call(["sudo", "apt-get", "update"])
                subprocess.check_call(["sudo", "apt-get", "install", "-y", "certbot"])
            elif shutil.which("yum"):
                subprocess.check_call(["sudo", "yum", "install", "-y", "certbot"])
            elif shutil.which("dnf"):
                subprocess.check_call(["sudo", "dnf", "install", "-y", "certbot"])
            else:
                print("❌ Could not install certbot automatically.")
                print("   Please install certbot manually and run this script again.")
                return False
        except subprocess.CalledProcessError:
            print("❌ Failed to install certbot.")
            return False

    cert_dir = Path(cert_dir)
    cert_dir.mkdir(exist_ok=True)

    try:
        # Generate certificate using standalone mode
        print(f"  🔄 Requesting certificate from Let's Encrypt...")
        print(f"  ⚠️  Make sure port 80 is available and {domain} points to this server!")

        cmd = [
            "sudo", "certbot", "certonly",
            "--standalone",
            "--agree-tos",
            "--no-eff-email",
            "--email", email,
            "-d", domain
        ]

        subprocess.check_call(cmd)

        # Copy certificates to our cert directory
        le_cert_dir = Path(f"/etc/letsencrypt/live/{domain}")
        if le_cert_dir.exists():
            shutil.copy2(le_cert_dir / "fullchain.pem", cert_dir / "cert.pem")
            shutil.copy2(le_cert_dir / "privkey.pem", cert_dir / "key.pem")

            print(f"✅ Let's Encrypt certificate set up successfully!")
            print(f"   📄 Certificate: {cert_dir / 'cert.pem'}")
            print(f"   🔑 Private key: {cert_dir / 'key.pem'}")
            print(f"   🔄 Auto-renewal: certbot will handle renewal automatically")
            return True
        else:
            print(f"❌ Certificate directory not found: {le_cert_dir}")
            return False

    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to obtain Let's Encrypt certificate: {e}")
        print("   Common issues:")
        print("   - Domain doesn't point to this server")
        print("   - Port 80 is not accessible from internet")
        print("   - Firewall blocking connections")
        return False

def print_browser_instructions():
    """Print instructions for bypassing browser security warnings"""
    print("\n" + "="*60)
    print("🌐 BROWSER SECURITY WARNING BYPASS INSTRUCTIONS")
    print("="*60)
    print()
    print("When using self-signed certificates, browsers will show security warnings.")
    print("Here's how to bypass them:")
    print()
    print("🔥 CHROME/EDGE:")
    print("  1. Click 'Advanced' on the warning page")
    print("  2. Click 'Proceed to localhost (unsafe)'")
    print("  3. Or type 'thisisunsafe' when on the warning page")
    print()
    print("🦊 FIREFOX:")
    print("  1. Click 'Advanced'")
    print("  2. Click 'Accept the Risk and Continue'")
    print()
    print("🍎 SAFARI:")
    print("  1. Click 'Show Details'")
    print("  2. Click 'visit this website'")
    print("  3. Click 'Visit Website' in the dialog")
    print()
    print("⚡ ALTERNATIVE SOLUTIONS:")
    print("  1. Use a reverse proxy like nginx with proper SSL")
    print("  2. Get a real SSL certificate from Let's Encrypt (free)")
    print("  3. Add the certificate to your browser's trusted certificates")
    print()
    print("🔗 For production use, consider:")
    print(f"   python3 {__file__} --letsencrypt --domain yourdomain.com --email your@email.com")
    print()

def main():
    parser = argparse.ArgumentParser(description="SSL Certificate Setup Tool for Hunyuan3D")
    parser.add_argument("--domain", default="localhost", help="Domain name for certificate")
    parser.add_argument("--cert-dir", default="./certs", help="Directory to store certificates")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--self-signed", action="store_true", help="Generate self-signed certificate")
    group.add_argument("--letsencrypt", action="store_true", help="Get Let's Encrypt certificate")

    parser.add_argument("--email", help="Email for Let's Encrypt (required with --letsencrypt)")
    parser.add_argument("--instructions", action="store_true", help="Show browser bypass instructions")

    args = parser.parse_args()

    if args.instructions:
        print_browser_instructions()
        return

    if args.letsencrypt:
        if not args.email:
            print("❌ Email is required for Let's Encrypt certificates")
            print("   Use: --email your@email.com")
            return

        if not setup_letsencrypt(args.domain, args.email, args.cert_dir):
            print("\n💡 Falling back to self-signed certificate...")
            generate_self_signed_cert(args.domain, args.cert_dir)
            print_browser_instructions()

    elif args.self_signed:
        if generate_self_signed_cert(args.domain, args.cert_dir):
            print_browser_instructions()

if __name__ == "__main__":
    # Import ipaddress here to avoid import at module level
    import ipaddress
    main()