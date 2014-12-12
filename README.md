```
$ yum -y install python-pip OR apt-get -y install python-pip
$ pip install python-etcd
$ pip install requests
$ pip install Flask
$ pip install docker-py
$ pip install PyYAML
$ pip install port-for
$ pip install --quiet https://storage.googleapis.com/archive.clusterhq.com/downloads/flocker/Flocker-0.3.2-py2-none-any.whl
```
Build:
```
$ docker build -t "ipanousis/armada-rest" .
```

Run:
```
$ docker run -d --net=host -i -t ipanousis/armada-rest
```

https://github.com/ipanousis/armada-rest/wiki
