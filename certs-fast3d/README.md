# SSL Certificate Management for fast3d.angel-lab.org

This directory contains scripts for managing Let's Encrypt SSL certificates for the domain `fast3d.angel-lab.org`.

## Initial Setup

1. **Update email address in scripts**:
   Edit `request_certificate.sh` and change the EMAIL variable to your actual email address.

2. **Request initial certificate**:
   ```bash
   sudo ./request_certificate.sh
   ```
   Note: Port 80 must be accessible from the internet for verification.

3. **Update your application** to use the new certificates:
   - Certificate: `certs-fast3d/fullchain.pem`
   - Private Key: `certs-fast3d/privkey.pem`

## Automatic Renewal

Let's Encrypt certificates expire every 90 days. Set up automatic renewal:

1. **Add to root's crontab**:
   ```bash
   sudo crontab -e
   ```

2. **Add this line** (runs daily at 2 AM):
   ```
   0 2 * * * /home/ubuntu/project/Hunyuan3D-2.1/certs-fast3d/renew_certificate.sh
   ```

3. **Or for user crontab with sudo**:
   ```bash
   crontab -e
   ```
   Add:
   ```
   0 2 * * * sudo /home/ubuntu/project/Hunyuan3D-2.1/certs-fast3d/renew_certificate.sh
   ```

## Manual Renewal Check

Run the renewal script manually:
```bash
sudo ./renew_certificate.sh
```

## Check Certificate Expiry

```bash
openssl x509 -enddate -noout -in fullchain.pem
```

## Logs

Renewal attempts are logged to: `certs-fast3d/renewal.log`

## Troubleshooting

1. **Port 80 not accessible**: Ensure firewall allows port 80 for certificate validation
2. **Domain not pointing to server**: Verify with `ping fast3d.angel-lab.org`
3. **Permission issues**: Scripts need sudo for certbot operations

## Using with start_https.sh

After obtaining certificates, update `start_https.sh` to use:
```bash
--ssl-certfile certs-fast3d/fullchain.pem \
--ssl-keyfile certs-fast3d/privkey.pem
```