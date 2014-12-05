import requests

is_flocker_runtime = lambda name : name.startswith('flocker--')

class State(object):

  configuration = None

  def __init__(self, configuration):
    self.configuration = configuration

  def get(self):
    state = requests.get('http://etcd.%s/v2/keys/?recursive=true' % self._get_cluster_name()).json()
    node_states = state['node']['nodes'][0]['nodes']
    return node_states

  def get_nodes(self):
    node_states = self.get()
    nodes = [node_state['key'].split('/')[-1] for node_state in node_states]
    return nodes

  def get_runtimes(self, flocker_only=False):
    node_states = self.get()
    runtimes = []
    for i, node in enumerate(node_states):
      node_runtimes = [eval(n['value']) for n in node['nodes']]
      print 'Number of containers on node %d: %d' % (i, len(node_runtimes))
      runtimes.extend(node_runtimes)
    if flocker_only:
      runtimes = [c for c in runtimes if is_flocker_runtime(c['name'])]
    return runtimes

  def _get_cluster_name(self):
    return self.configuration.get('default', 'name')