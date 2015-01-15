#!/usr/bin/env python

import json
import yaml
import etcd
import state
import docker
import os.path
import subprocess
import itertools
import ConfigParser as cp

from flask import Flask, request
from flask.ext.cors import CORS
from multiprocessing import Pool

import flocker_config.application as app_lib
import flocker_config.deployment as dep_lib

is_flocker_runtime = lambda name : name.startswith('flocker--')

ETC = '/etc/armada-rest'

get_configuration = lambda file : os.path.join(ETC, file)

FILE_CLUSTER_PROPERTIES = get_configuration('armada-rest.properties')
TMP_APP_YML = '/tmp/application.yml'
TMP_DEP_YML = '/tmp/deployment.yml'

config = cp.ConfigParser()
config.readfp(open(FILE_CLUSTER_PROPERTIES,'r'))

app = Flask(__name__)
cors = CORS(app)

def get_cluster_name():
  return config.get('default', 'name')

etcd_client = etcd.Client(host='etcd.%s' % get_cluster_name(),port=80)
flocker_state = state.State(etcd_client)

def get_content_from_stream(upload_stream):
  file_string = ''.join(upload_stream.readlines())
  return file_string

def write_yaml(yaml_filename, yaml_object):
  with open(yaml_filename, 'w') as yaml_file:
    yaml_file.write(yaml.dump(yaml_object))

def flocker_deploy(deployment_yml, application_yml):
  write_yaml(TMP_APP_YML, application_yml)
  write_yaml(TMP_DEP_YML, deployment_yml)
  proc = subprocess.Popen('flocker-deploy %s %s' % (TMP_DEP_YML, TMP_APP_YML),
                          shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  result = proc.communicate()
  return result[0], result[1]

@app.route('/flocker/runtimes', methods = ['GET'])
def get_runtimes():
  flocker_only = request.args.get('flocker_only', False)
  runtimes = { 'runtimes' : flocker_state.get_runtimes(flocker_only) }
  return json.dumps(runtimes, indent=4)

@app.route('/flocker/runtime/<application>', methods = ['GET'])
def get_runtime(application):
  not_flocker = request.args.get('not_flocker', False)
  flocker_prefix = ('' if not_flocker else 'flocker--')
  runtime = flocker_state.get_runtime(flocker_prefix + application)
  if runtime != None:
    return json.dumps(flocker_state.get_runtime(flocker_prefix + application), indent=4)
  else:
    return 'Runtime %s not found' % application, 404

@app.route('/flocker/runtime/<application>/port/<port>', methods = ['GET'])
def get_runtime_port(application, port):
  not_flocker = request.args.get('not_flocker', False)
  flocker_prefix = ('' if not_flocker else 'flocker--')
  runtime = flocker_state.get_runtime(flocker_prefix + application)
  requested_port = [each_port['external'] for each_port in runtime['ports'] if port == each_port['internal']]
  if len(requested_port) == 0:
    return 'Port %d requested not found for application %s' % (port, application), 404
  return str(requested_port[0])

@app.route('/flocker/nodes', methods = ['GET'])
def get_nodes():
  nodes = { 'nodes' : flocker_state.get_nodes() }
  return json.dumps(nodes, indent=4)

def pull_image_star(args):
  return pull_image(*args)

def pull_image(node, image):
  docker_client = docker.Client(base_url='tcp://%s:4243' % node)
  return docker_client.pull(image, insecure_registry=True)

@app.route('/flocker/image/<path:image>', methods = ['PUT'])
def put_image(image):
  nodes = list(flocker_state.get_nodes())
  pool = Pool(len(nodes))
  results = pool.map(pull_image_star, itertools.izip(nodes, itertools.repeat(image)))
  pool.close()
  pool.join()
  return 'Image successfully pulled: %s' % image

def check_is_image_pulled(image):
  repository, tag = image.split(':')[0], 'latest' if not ':' in image else image.split(':')[1]
  nodes = flocker_state.get_nodes()
  for node in nodes:
    cli = docker.Client(base_url='tcp://%s:4243' % node)
    image_objects = cli.images(repository)
    if len(image_objects) == 0:
      return False
    images_with_tags = []
    [images_with_tags.extend(i['RepoTags']) for i in image_objects]
    tags = [i.split(':')[1] for i in images_with_tags]
    if not tag in tags:
      return False
  return True

@app.route('/flocker/runtime/<runtime>', methods=['PUT'])
def put_runtime(runtime):
  uploaded_files = request.files.values()
  if len(uploaded_files) == 0:
    return 'No application YAML was uploaded', 401
  file_string = get_content_from_stream(uploaded_files[0].stream)

  new_application = app_lib.load_new(file_string)
  runtime = str(runtime) # convert from u'xx' to 'xx'
  new_application = { 'name' : runtime, 'yml' : { runtime : new_application['yml'].values()[0] } }

  image = new_application['yml'][runtime]['image']
  is_pulled = check_is_image_pulled(image)
  if not is_pulled:
    return 'Image not pulled yet: %s' % image, 404

  current_runtimes = flocker_state.get_runtimes(flocker_only=True)

  current_applications = app_lib.load_current_from_etcd(current_runtimes, etcd_client)

  new_applications = app_lib.add_new_application(current_applications, current_runtimes, new_application, etcd_client)

  current_deployments = dep_lib.load_current(current_runtimes)

  new_deployments = dep_lib.add_new_deployment(current_deployments, new_application['name'])

  print new_applications['yml']
  print new_deployments
  stdout, stderr = flocker_deploy(new_deployments, new_applications['yml'])
  return json.dumps({ 'stdout' : stdout, 'stderr' : stderr }, indent=4)

@app.route('/flocker/runtime/<runtime>', methods = ['DELETE'])
def delete_runtime(runtime):
  runtime = str(runtime)
  print runtime
  if flocker_state.get_runtime(runtime) == None:
    return 'Runtime %s not found' % runtime, 404

  current_runtimes = flocker_state.get_runtimes(flocker_only=True)

  current_applications = app_lib.load_current_from_etcd(current_runtimes, etcd_client)

  current_deployments = dep_lib.load_current(current_runtimes)

  del current_applications['yml'][runtime]

  nodes = [node for node, node_applications in current_deployments['nodes'].iteritems() if runtime in node_applications]

  for node in nodes:
    current_deployments['nodes'][node].remove(runtime)

  print current_applications['yml']
  print current_deployments
  stdout, stderr = flocker_deploy(current_deployments, current_applications['yml'])
  return json.dumps({ 'stdout' : stdout, 'stderr' : stderr }, indent=4)

if __name__ == '__main__':
  # this should not really be threaded because flocker-deploy should not be run in parallel
  # however it is very slow when single-threaded, so solving this problem is top priority
  # TODO: make put_runtime endpoint work asynchronously by adding a creation task to a queue
  app.run(host='0.0.0.0', debug=True, threaded=True)
