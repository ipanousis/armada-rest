#!/usr/bin/env python

import pdb
import json
import yaml
import docker
import port_for
import requests
import subprocess
import ConfigParser as cp

from flask import Flask, request

app = Flask(__name__)

config = cp.ConfigParser()
config.readfp(open('cluster.properties','r'))

port_store = port_for.store.PortStore()

is_flocker_runtime = lambda name : name.startswith('flocker--')
get_app_name_from_runtime_name = lambda name : name.replace('flocker--', '')

def unbind_all_ports():
  [port_store.unbind_port(bound_port_mapping[0]) for bound_port_mapping in port_store.bound_ports()]

def get_cluster_name():
  return config.get('default','name')

@app.route('/flocker/runtimes', methods = ['GET'])
def get_runtimes(flocker_only=False):
  flocker_only = request.args.get('flocker_only', flocker_only)
  node_states = json.loads(get_state())
  node_states = node_states['state']
  runtimes = []
  for i, node in enumerate(node_states):
    node_runtimes = [eval(n['value']) for n in node['nodes']]
    print 'Number of containers on node %d: %d' % (i, len(node_runtimes))
    runtimes.extend(node_runtimes)
  if flocker_only:
    runtimes = [c for c in runtimes if is_flocker_runtime(c['name'])]
  runtimes = { 'runtimes' : runtimes }
  return json.dumps(runtimes, indent=4)

@app.route('/flocker/nodes', methods = ['GET'])
def get_nodes():
  node_states = json.loads(get_state())
  node_states = node_states['state']
  print 'Number of cluster nodes:', len(node_states)
  nodes = [node_state['key'].split('/')[-1] for node_state in node_states]
  nodes = { 'nodes' : nodes }
  return json.dumps(nodes, indent=4)

@app.route('/flocker/state')
def get_state():
  state = requests.get('http://etcd.%s/v2/keys/?recursive=true' % get_cluster_name()).json()
  node_states = state['node']['nodes'][0]['nodes']
  node_states = { 'state' : node_states }
  return json.dumps(node_states, indent=4)

@app.route('/flocker/image/<path:image>', methods = ['PUT'])
def put_image(image):
  print image, request.args
  if request.args.has_key('tag'):
    image = image + ':' + request.args.get('tag')
  nodes = json.loads(get_nodes())
  nodes = nodes['nodes']
  for node in nodes:
    cli = docker.Client(base_url='tcp://%s:4243' % node)
    for line in cli.pull(image, stream=True):
      print(json.dumps(json.loads(line), indent=4))
  return 'True'

@app.route('/flocker/runtime', methods=['PUT'])
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

  # change external ports to a random port
  current_external_ports = []
  for runtime in runtimes:
    current_external_ports.extend([int(port['external']) for port in runtime['ports'] if port['external'] != None])
  available_external_ports = port_for.available_good_ports().difference(set(current_external_ports))
  
  new_runtime_internal_ports = [port[max(port.find(':') + 1, 0):] for port in new_runtime_config[new_runtime_name]['ports']]
  new_runtime_internal_ports = [int(port) for port in new_runtime_internal_ports]
  new_port_mappings = []

  unbind_all_ports()
  for internal_port in new_runtime_internal_ports:
    bound_port_name = new_runtime_name + '-' + str(internal_port)
    external_port = port_store.bind_port(bound_port_name)
    new_port_mappings.append('%d:%d' % (external_port, internal_port))
  unbind_all_ports()

  new_runtime_config[new_runtime_name]['ports'] = new_port_mappings
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

  proc = subprocess.Popen('flocker-deploy deployment.yml application.yml', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  print proc.communicate()

  return 'True'

@app.route('/flocker/runtime', methods = ['DELETE'])
def delete_runtime():
  pass

if __name__ == '__main__':
  app.run(host='0.0.0.0', debug=True)
