is_flocker_runtime = lambda name : name.startswith('flocker--')

class State(object):

  etcd_client = None

  def __init__(self, etcd_client):
    self.etcd_client = etcd_client

  def get_nodes(self):
    runtimes = self._get_runtimes()
    return list(set([runtime['host'] for runtime in runtimes]))

  def get_runtimes(self, flocker_only=False):
    runtimes = self._get_runtimes()
    if flocker_only:
      runtimes = [c for c in runtimes if is_flocker_runtime(c['name'])]
    return list(runtimes)

  def _get_cluster_name(self):
    return self.configuration.get('default', 'name')

  def _get_runtimes(self):
    backend_nodes = self.etcd_client.read('backends', recursive=True)
    for backend_node in backend_nodes.children:
      for backend_node_runtime in backend_node.get_subtree():
        yield eval(backend_node_runtime.value)