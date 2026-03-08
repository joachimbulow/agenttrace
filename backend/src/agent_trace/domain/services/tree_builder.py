from __future__ import annotations

from typing import TYPE_CHECKING

from ..entities import TraceNode

if TYPE_CHECKING:
    from ..entities import TraceNode


class TreeBuilder:
    """Service for building hierarchical trace trees from flat node lists.

    This is a pure domain service with no infrastructure dependencies.
    It takes a flat list of TraceNode objects and builds a tree structure
    by setting parent-child relationships.
    """

    @staticmethod
    def build_tree(nodes: list[TraceNode]) -> list[TraceNode]:
        """Build hierarchical trees from flat node list.

        Takes a flat list of nodes and builds trees by:
        1. Creating a lookup dict by node ID
        2. Linking children to parents
        3. Returning root nodes (nodes with no parent)

        Args:
            nodes: Flat list of TraceNode objects.

        Returns:
            List of root nodes with children populated.

        Example:
            >>> nodes = [
            ...     TraceNode(id="1", run_id="r1", name="root", span_type=SpanType.AGENT_RUN, parent_id=None),
            ...     TraceNode(id="2", run_id="r1", name="child", span_type=SpanType.STEP, parent_id="1"),
            ... ]
            >>> roots = TreeBuilder.build_tree(nodes)
            >>> len(roots)
            1
            >>> len(roots[0].children)
            1
        """
        if not nodes:
            return []

        # Create lookup dict
        node_map: dict[str, TraceNode] = {node.id: node for node in nodes}

        # Clear children (in case nodes were reused)
        for node in nodes:
            node.children = []

        # Link children to parents
        root_nodes: list[TraceNode] = []
        for node in nodes:
            if node.parent_id is None:
                # Root node
                root_nodes.append(node)
            elif node.parent_id in node_map:
                # Add as child to parent
                parent = node_map[node.parent_id]
                parent.add_child(node)
            # If parent_id not found, node is orphaned (log warning in real app)

        return root_nodes

    @staticmethod
    def flatten_tree(roots: list[TraceNode]) -> list[TraceNode]:
        """Flatten hierarchical trees to flat node list.

        Performs depth-first traversal to create a flat list.

        Args:
            roots: List of root nodes with children.

        Returns:
            Flat list of all nodes in depth-first order.

        Example:
            >>> root = TraceNode(id="1", run_id="r1", name="root", span_type=SpanType.AGENT_RUN, parent_id=None)
            >>> child = TraceNode(id="2", run_id="r1", name="child", span_type=SpanType.STEP, parent_id="1")
            >>> root.add_child(child)
            >>> flat = TreeBuilder.flatten_tree([root])
            >>> len(flat)
            2
            >>> flat[0].id
            "1"
            >>> flat[1].id
            "2"
        """
        result: list[TraceNode] = []

        def traverse(node: TraceNode) -> None:
            """Recursively traverse tree."""
            result.append(node)
            for child in node.children:
                traverse(child)

        for root in roots:
            traverse(root)

        return result

    @staticmethod
    def find_node(roots: list[TraceNode], node_id: str) -> TraceNode | None:
        """Find a node by ID in the tree.

        Performs depth-first search.

        Args:
            roots: List of root nodes.
            node_id: ID of node to find.

        Returns:
            TraceNode if found, None otherwise.
        """

        def search(node: TraceNode) -> TraceNode | None:
            """Recursively search for node."""
            if node.id == node_id:
                return node
            for child in node.children:
                found = search(child)
                if found:
                    return found
            return None

        for root in roots:
            found = search(root)
            if found:
                return found

        return None

    @staticmethod
    def get_depth(node: TraceNode, node_map: dict[str, TraceNode] | None = None) -> int:
        """Calculate the depth of a node in the tree.

        Args:
            node: Node to calculate depth for.
            node_map: Optional lookup dict mapping node IDs to nodes.
                      Required for accurate depth calculation if parent
                      references are not embedded in nodes.

        Returns:
            Depth of the node (0 for root nodes).
        """
        depth = 0
        current_id = node.parent_id

        while current_id is not None and node_map is not None:
            depth += 1
            parent = node_map.get(current_id)
            if parent is None:
                break
            current_id = parent.parent_id

        return depth

    @staticmethod
    def count_nodes(roots: list[TraceNode]) -> int:
        """Count total nodes in trees.

        Args:
            roots: List of root nodes.

        Returns:
            Total count of all nodes.
        """
        flat = TreeBuilder.flatten_tree(roots)
        return len(flat)

    @staticmethod
    def count_by_type(roots: list[TraceNode]) -> dict[str, int]:
        """Count nodes by span type.

        Args:
            roots: List of root nodes.

        Returns:
            Dictionary mapping span_type value to count.
        """
        from ..value_objects import SpanType

        flat = TreeBuilder.flatten_tree(roots)
        counts: dict[str, int] = {}

        for node in flat:
            type_value = node.span_type.value
            counts[type_value] = counts.get(type_value, 0) + 1

        return counts
