#!/bin/bash
# Install Docker if not present
if ! command -v docker &> /dev/null
then
    amazon-linux-extras install docker -y
    systemctl start docker
    usermod -a -G docker ec2-user
fi
