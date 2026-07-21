# OMVS Nikto Guide

`nikto -h http://mainframe:8080/manager/html -id tomcat:tomcat -C all` produces a Nikto-style Tomcat Manager finding. In Gibson vuln mode, default Tomcat credentials are accepted. In secure mode, they are rejected.
