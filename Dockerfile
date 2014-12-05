FROM centos:centos7

RUN yum -y install https://download.fedoraproject.org/pub/epel/7/x86_64/e/epel-release-7-2.noarch.rpm
RUN yum -y install python-pip gcc python-devel openssh
RUN pip install requests Flask docker-py PyYAML port-for fabric
RUN pip install supervisor
RUN pip install --upgrade pip
RUN pip install --quiet https://storage.googleapis.com/archive.clusterhq.com/downloads/flocker/Flocker-0.3.2-py2-none-any.whl

RUN mkdir -p /var/log/supervisor
RUN mkdir -p /etc/supervisor/conf.d

EXPOSE 5000

ADD . /app
ADD etc /etc

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisord.conf"]
