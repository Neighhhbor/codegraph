import networkx as nx

class RepoSearcher:
    def __init__(self, graph):
        self.graph = graph

    def one_hop_neighbors(self, query):
        # 获取 1-hop 邻居
        return list(self.graph.neighbors(query))

    def two_hop_neighbors(self, query):
        # 获取 2-hop 邻居
        one_hop = self.one_hop_neighbors(query)
        two_hop = set()
        for node in one_hop:
            two_hop.update(self.one_hop_neighbors(node))
        return list(two_hop - set([query]))  # 移除起始节点自身

    def k_hop_neighbors(self, query, k):
        # 获取 k-hop 邻居
        visited = set()
        current_level = set([query])
        for _ in range(k):
            next_level = set()
            for node in current_level:
                next_level.update(self.graph.neighbors(node))
            visited.update(current_level)
            current_level = next_level - visited
        return list(current_level)

    def dfs(self, query, depth):
        # 使用 DFS 查询指定深度的节点
        visited = set()
        stack = [(query, 0)]
        result = []
        while stack:
            node, level = stack.pop()
            if node not in visited:
                visited.add(node)
                result.append(node)
                if level < depth:
                    stack.extend([(n, level + 1) for n in self.graph.neighbors(node)])
        return result
    
    def bfs(self, query, depth):
        # 使用 BFS 查询指定深度的节点
        visited = set()
        queue = [(query, 0)]
        result = []
        while queue:
            node, level = queue.pop(0)
            if node not in visited:
                visited.add(node)
                result.append(node)
                if level < depth:
                    queue.extend([(n, level + 1) for n in self.graph.neighbors(node)])
        return result
