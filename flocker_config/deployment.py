
get_app_name_from_runtime_name = lambda name : name.replace('flocker--', '')

def load_current(runtimes):
  nodes = set([runtime['host'] for runtime in runtimes])
  dep_config = {}
  [dep_config.__setitem__(str(node), []) for node in nodes]
  for runtime in runtimes:
    app = get_app_name_from_runtime_name(str(runtime['name']))
    dep_config[runtime['host']].append(app)
  dep_config = { "version" : 1, "nodes" : dep_config }
  return dep_config

def add_new_deployment(current_deployments, new_deployment):
  least_apps_node = min(current_deployments['nodes'].keys(), key = (lambda node : len(current_deployments['nodes'][node])))
  current_deployments['nodes'][least_apps_node].append(new_deployment)
  return current_deployments