#!/usr/bin/env python

import pdb
import json
import yaml
import docker
import requests
import ConfigParser as cp

from flask import Flask, request

app = Flask(__name__)

config = cp.ConfigParser()
config.readfp(open('cluster.properties','r'))

def get_cluster_name():
  return config.get('default','name')

@app.route('/')
def hello_world():
  return 'Hello World!'

is_flocker_container = lambda name : name.startswith('flocker--')
get_app_name_from_runtime_name = lambda name : name.replace('flocker--', '')

@app.route('/docker/runtimes')
def get_runtimes(flocker_only=False):
  flocker_only = request.args.get('flocker_only', flocker_only)
  state = requests.get('http://etcd.%s/v2/keys/?recursive=true' % get_cluster_name()).json()
  nested = state['node']['nodes'][0]
  print 'Number of cluster nodes:', len(nested['nodes'])
  cluster_nodes = nested['nodes']
  containers = []
  for i, node in enumerate(cluster_nodes):
    node_containers = [eval(n['value']) for n in node['nodes']]
    print 'Number of containers on node %d: %d' % (i, len(node_containers))
    containers.extend(node_containers)
  if flocker_only:
    containers = [c for c in containers if is_flocker_container(c['name'])]
  runtimes = { 'runtimes' : containers }
  return str(json.dumps(runtimes,indent=4))

@app.route('/docker/image/<path:image>', methods=['PUT'])
def put_image(image):
  print image, request.args
  if request.args.has_key('tag'):
    image = image + ':' + request.args.get('tag')
  nodes = ['10.240.202.202', '10.240.112.213']
  for node in nodes:
    cli = docker.Client(base_url='tcp://%s:4243' % node)
    for line in cli.pull(image, stream=True):
      print(json.dumps(json.loads(line), indent=4))
  return 'True'

@app.route('/docker/runtime', methods=['PUT'])
def put_runtime():
  uploaded_files = request.files.values()
  assert len(uploaded_files) > 0

  file_stream = uploaded_files[0].stream
  file_lines = ''.join(file_stream.readlines())

  new_runtime_config = yaml.load(file_lines)

  assert len(new_runtime_config.keys()) == 1

  new_runtime_name = new_runtime_config.keys()[0]

  # ultimate version:
  # get state from etcd in order to get running containers
  # inspect those containers and derive their fig.yml
  # reconstruct application.yml yaml string
  # 
  # process the given fig.yml for its exposed port to be random
  # append given fig.yml to applicaiton.yml yaml string
  # choose a node to deploy this runtime to
  # reconstruct deployment.yml yaml string

  runtimes = json.loads(get_runtimes(flocker_only=True))
  runtimes = runtimes['runtimes']

  print runtimes
  
  app_config_file = open('application.yml', 'r')
  app_config = ''.join(app_config_file.readlines())
  app_config_file.close()
  app_config = yaml.load(app_config)

  print app_config

  print new_runtime_config

  assert new_runtime_name not in app_config.keys()

  app_config.update(new_runtime_config)
  
  print app_config
 
  dep_config = {}
  nodes = set([runtime['host'] for runtime in runtimes])
  [dep_config.__setitem__(str(node), []) for node in nodes]
  for runtime in runtimes:
    app = get_app_name_from_runtime_name(str(runtime['name']))
    dep_config[runtime['host']].append(app)

  least_apps_node = min(dep_config.keys(), key = (lambda node : len(dep_config[node])))

  dep_config[least_apps_node].append(new_runtime_name)

  dep_config = { "version" : 1, "nodes" : dep_config }

  print dep_config

  app_yml = open('application.yml', 'w')
  app_yml.write(yaml.dump(app_config))
  app_yml.close()

  dep_yml = open('deployment.yml', 'w')
  dep_yml.write(yaml.dump(dep_config))
  dep_yml.close()

  return 'True'

if __name__ == '__main__':
  app.run(host='0.0.0.0', debug=True)
