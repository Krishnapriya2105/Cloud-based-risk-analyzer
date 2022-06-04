#!/bin/bash
#yum update -y
yum install httpd -y
service httpd start
chkconfig httpd on
python3 -m pip install boto3
# file ownership permissions also
wget https://extreme-sinner.ew.r.appspot.com/cacheavoid/risk_analysis.py -P /var/www/cgi-bin
chmod +x /var/www/cgi-bin/risk_analysis.py
 
#wget https://extreme-signer-340616.ew.r.appspot.com/cacheavoid/sshd_config -O /etc/ssh/sshd_config
#service sshd restart




