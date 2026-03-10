#!/bin/bash
JFROG_URL="https://edshopdpt8.jfrog.io/artifactory/libs-release-local/com/devopsrealtime/dptweb/1.0/dptweb-1.0.war"

wget --user=$JFROG_USERNAME --password=$JFROG_ACCESS_TOKEN \
    -O /opt/tomcat/webapps/ROOT.war $JFROG_URL
sudo systemctl restart tomcat
