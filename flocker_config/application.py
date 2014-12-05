import yaml
import port_for

def load_new(app_yaml_string):
  new_runtime_config = yaml.load(app_yaml_string)
  assert len(new_runtime_config.keys()) == 1
  new_runtime_name = new_runtime_config.keys()[0]
  return { 'name' : new_runtime_name, 'yml' : new_runtime_config }

def load_current(app_yaml_string):
  current_config = yaml.load(app_yaml_string)
  return { 'names' : current_config.keys(), 'yml' : current_config }

def load_current_from_file(app_yaml_filename):
  app_config_file = open(app_yaml_filename, 'r')
  app_config_string = ''.join(app_config_file.readlines())
  app_config_file.close()
  return load_current(app_config_string)

def add_new_application(current_applications, current_runtimes, new_application):
  new_application_name = new_application['name']
  assert new_application_name not in current_applications['names']

  # change external ports to a random port
  current_external_ports = []
  for runtime in current_runtimes:
    current_external_ports.extend([int(port['external']) for port in runtime['ports'] if port['external'] != None])
  available_external_ports = port_for.available_good_ports().difference(set(current_external_ports))

  new_runtime_internal_ports = [port[max(port.find(':') + 1, 0):] for port in new_application['yml'][new_application_name]['ports']]
  new_runtime_internal_ports = [int(port) for port in new_runtime_internal_ports]
  new_port_mappings = []

  for internal_port in new_runtime_internal_ports:
    external_port = available_external_ports.pop()
    new_port_mappings.append('%d:%d' % (external_port, internal_port))

  new_application['yml'][new_application_name]['ports'] = new_port_mappings
  current_applications['yml'].update(new_application['yml'])

  return current_applications