#!/usr/bin/env python

import sys
import json
import yaml
import etcd
import state
import docker
import shutil
import os.path
import subprocess
import ConfigParser as cp

from flask import Flask, request
from flask.ext.cors import CORS

import flocker_config.application as app_lib
import flocker_config.deployment as dep_lib

is_flocker_runtime = lambda name : name.startswith('flocker--')

ETC = sys.argv[1]

get_configuration = lambda file : os.path.join(ETC, file)

FILE_CLUSTER_PROPERTIES = get_configuration('cluster.properties')
FILE_APP_YML = get_configuration('application.yml')
FILE_DEP_YML = get_configuration('deployment.yml')

config = cp.ConfigParser()
config.readfp(open(FILE_CLUSTER_PROPERTIES,'r'))

app = Flask(__name__)
cors = CORS(app)

etcd_client = etcd.Client(host='etcd.flocker.kalamia.in',port=80)
flocker_state = state.State(etcd_client)

def get_cluster_name():
  return config.get('default', 'name')

def get_content_from_stream(upload_stream):
  file_string = ''.join(upload_stream.readlines())
  return file_string

def write_yaml(yaml_filename, yaml_object):
  with open(yaml_filename, 'w') as yaml_file:
    yaml_file.write(yaml.dump(yaml_object))

@app.route('/flocker/runtimes', methods = ['GET'])
def get_runtimes():
  flocker_only = request.args.get('flocker_only', False)
  runtimes = { 'runtimes' : flocker_state.get_runtimes(flocker_only) }
  return json.dumps(runtimes, indent=4)

@app.route('/flocker/nodes', methods = ['GET'])
def get_nodes():
  nodes = { 'nodes' : flocker_state.get_nodes() }
  return json.dumps(nodes, indent=4)

@app.route('/flocker/image/<path:image>', methods = ['PUT'])
def put_image(image):
  if request.args.has_key('tag'):
    image = image + ':' + request.args.get('tag')
  nodes = flocker_state.get_nodes()
  for node in nodes:
    cli = docker.Client(base_url='tcp://%s:4243' % node)
    for line in cli.pull(image, stream=True):
      print(json.dumps(json.loads(line), indent=4))
  return 'True'

@app.route('/flocker/runtime', methods=['PUT'])
def put_runtime():
  # ultimate version:
  # get state from etcd in order to get running containers
  # inspect those containers and derive their fig.yml
  # reconstruct application.yml yaml string
  #
  # process the given fig.yml for its exposed port to be random
  # append given fig.yml to applicaiton.yml yaml string
  # choose a node to deploy this runtime to
  # reconstruct deployment.yml yaml string

  uploaded_files = request.files.values()
  assert len(uploaded_files) > 0
  file_string = get_content_from_stream(uploaded_files[0].stream)

  current_runtimes = flocker_state.get_runtimes(flocker_only=True)

  new_application = app_lib.load_new(file_string)

  current_applications = app_lib.load_current_from_etcd(current_runtimes, etcd_client)

  new_applications = app_lib.add_new_application(current_applications, current_runtimes, new_application, etcd_client)

  current_deployments = dep_lib.load_current(current_runtimes)

  new_deployments = dep_lib.add_new_deployment(current_deployments, new_application['name'])

  print new_applications['yml']
  print new_deployments

  write_yaml(FILE_APP_YML, new_applications['yml'])
  write_yaml(FILE_DEP_YML, new_deployments)

  proc = subprocess.Popen('flocker-deploy %s %s' % (FILE_DEP_YML, FILE_APP_YML),
                          shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  result = proc.communicate()
  return json.dumps({ 'stdout' : result[0], 'stderr' : result[1] }, indent=4)

@app.route('/flocker/runtime/<runtime>', methods = ['DELETE'])
def delete_runtime(runtime):

  current_runtimes = flocker_state.get_runtimes(flocker_only=True)

  current_applications = app_lib.load_current_from_etcd(current_runtimes, etcd_client)

  current_deployments = dep_lib.load_current(current_runtimes)

  del current_applications['yml'][runtime]

  nodes = [node for node, node_applications in current_deployments['nodes'].iteritems() if runtime in node_applications]

  for node in nodes:
    current_deployments['nodes'][node].remove(runtime)

  print current_applications['yml']
  print current_deployments

  write_yaml(FILE_APP_YML, current_applications['yml'])
  write_yaml(FILE_DEP_YML, current_deployments)
  proc = subprocess.Popen('flocker-deploy %s %s' % (FILE_DEP_YML, FILE_APP_YML),
                          shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  result = proc.communicate()
  return result[0]

if __name__ == '__main__':
  # this should not really be threaded because flocker-deploy should not be run in parallel
  # however it is very slow when single-threaded, so solving this problem is top priority
  # TODO: make put_runtime endpoint work asynchronously by adding a creation task to a queue
  app.run(host='0.0.0.0', debug=True, threaded=True)
