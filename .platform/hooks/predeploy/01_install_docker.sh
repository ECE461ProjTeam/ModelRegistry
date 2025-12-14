#!/bin/bash
# Install Docker if not present
if ! command -v docker &> /dev/null
then
    yum install docker -y
    systemctl start docker
    sudo usermod -a -G docker ec2-user
fi
