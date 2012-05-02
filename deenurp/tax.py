"""
Representation of a taxonomic tree.
"""

import collections
import csv

class TaxNode(object):
    """
    Taxonomic tree, with optional sequence IDs on nodes
    """
    def __init__(self, rank, tax_id, parent=None, sequence_ids=None, children=None, name=None):
        self.ranks = None
        self.rank = rank
        self.name = name
        self.tax_id = tax_id
        self.parent = parent
        self.sequence_ids = sequence_ids or []
        self.children = children or []
        assert tax_id != ""

        if self.is_root:
            self.index = {self.tax_id: self}

    def add_child(self, child):
        """
        Add a child to this node
        """
        child.parent = self
        child.ranks = self.ranks
        child.index = self.index
        assert child.tax_id not in self.index
        self.index[child.tax_id] = child
        self.children.append(child)

    def remove_child(self, child):
        """
        Remove a child from this node
        """
        assert child in self.children
        self.children.remove(child)
        self.index.pop(child.tax_id)
        if child.parent == self:
            child.parent = None
        if child.index == self.index:
            child.index = None

    def prune_unrepresented(self):
        """
        Remove taxa without sequences in the subtree below
        """
        def below(node):
            any_below = any(below(child) for child in self.children)
            if not any_below and not self.children:
                self.parent.remove_child(self)
                return False
            return True

        below(self)

    @property
    def is_leaf(self):
        return not self.children

    @property
    def is_root(self):
        return self.parent is None

    def at_rank(self, rank):
        """
        Find the node in this node's lineage at rank ``rank``
        """
        s = self
        while s:
            if s.rank == rank:
                return s
            s = s.parent
        raise KeyError("No node at rank {0} for {1}".format(rank,
            self.tax_id))

    def depth_first_iter(self):
        """
        Iterate over nodes in the tree, returning children before self.
        """
        yield self
        for child in self.children:
            for i in child.depth_first_iter():
                yield i

    def subtree_sequence_ids(self):
        """
        Generate all sequence IDs at or below this node.
        """
        for node in self:
            for s in node.sequence_ids:
                yield s

    def path(self, tax_ids):
        """Get the node at the end of the path described by tax_ids"""
        assert tax_ids[0] == self.tax_id
        if len(tax_ids) == 1:
            return self

        n = tax_ids[1]
        try:
            child = next(i for i in self.children if i.tax_id == n)
        except StopIteration:
            raise KeyError(n)

        return child.path(tax_ids[1:])

    def get_node(self, tax_id):
        """
        Get a node by tax id
        """
        return self.index[tax_id]

    def lineage(self):
        """
        Return all nodes between this node and the root, including this one.
        """
        if not self.parent: return [self]
        else:
            l = self.parent.lineage()
            l.append(self)
            return l

    def __repr__(self):
        return "<TaxNode {0}:{1} [rank={2};children={3}]>".format(self.tax_id,
                self.name, self.rank, len(self.children))

    def __iter__(self):
        return self.depth_first_iter()

    def write_taxtable(self, out_fp, **kwargs):
        """
        Write a taxtable for this node and all descendants,
        including the lineage leading to this node.
        """
        ranks_represented = frozenset(i.rank for i in self) | \
                            frozenset(i.rank for i in self.lineage())
        ranks = [i for i in self.ranks if i in ranks_represented]
        assert len(ranks_represented) == len(ranks)

        def node_record(node):
            parent_id = node.parent.tax_id if node.parent else node.tax_id
            d = {'tax_id': node.tax_id,
                 'tax_name': node.name,
                 'parent_id': parent_id,
                 'rank': node.rank}
            l = {i.rank: i.tax_id for i in node.lineage()}
            d.update(l)
            return d

        def node_iter(node):
            yield node
            for child in node.children:
                for i in node_iter(child):
                    yield i

        header = ['tax_id', 'parent_id', 'rank', 'tax_name'] + ranks
        w = csv.DictWriter(out_fp, header, quoting=csv.QUOTE_NONNUMERIC,
                lineterminator='\n')
        w.writeheader()
        # All nodes leading to this one
        for i in self.lineage()[:-1]:
            w.writerow(node_record(i))
        w.writerows(node_record(i) for i in node_iter(self))

    @classmethod
    def from_taxtable(cls, taxtable_fp):
        """
        Generate a node from an open handle to a taxtable, as generated by
        ``taxit taxtable``
        """
        r = csv.reader(taxtable_fp)
        headers = next(r)
        rows = (collections.OrderedDict(zip(headers, i)) for i in r)

        row = next(rows)
        root = cls(rank=row['rank'], tax_id=row['tax_id'], name=row['tax_name'])
        root.ranks = headers[4:]
        for row in rows:
            rank, tax_id, name = [row[i] for i in ('rank', 'tax_id', 'tax_name')]
            path = filter(None, row.values()[4:])
            parent = root.path(path[:-1])
            parent.add_child(cls(rank, tax_id, name=name))

        return root

    @classmethod
    def from_taxdb(cls, con, root=None):
        """
        Generate a TaxNode from a taxonomy database
        """
        cursor = con.cursor()
        if root is None:
            cursor.execute("SELECT tax_id, rank FROM nodes WHERE tax_id = parent_id")
        else:
            cursor.execute("SELECT tax_id, rank FROM nodes WHERE tax_id = ?", [root])

        tax_id, rank = cursor.fetchone()
        root = cls(rank=rank, tax_id=tax_id)

        def add_lineage(parent):
            cursor.execute("""SELECT tax_id, rank, tax_name
                    FROM nodes INNER JOIN names USING (tax_id)
                    WHERE parent_id = :1 and tax_id <> :1
                        AND names.is_primary = 1
                    """, [parent.tax_id])
            for tax_id, rank, name in cursor:
                node = cls(rank=rank, tax_id=tax_id, name=name)
                parent.add_child(node)
            for child in parent.children:
                add_lineage(child)

        add_lineage(root)
        return root
