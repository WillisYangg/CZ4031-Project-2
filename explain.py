import psycopg2
import configparser
from collections import deque
import sqlparse
from pprint import pprint
import networkx as nx
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np


#recursively builds itself in a depth first search manner
class Node:
    def __init__(self,information, parent=None):
        self.parent = parent
        self.index = None
        self.reasons = []
        self.children = []
        self.node_type = information['Node Type']
        del information['Node Type']
        self.information = information
        if 'Plans' in information:
            plans = information['Plans']
            del information['Plans']
            for plan in plans:
                child = Node(plan, self)
                self.children.append(child)

def connect_db():
    config = configparser.ConfigParser()
    config.read('config.ini')
    default = config['DEFAULT']
    return psycopg2.connect(
        host=default['DB_HOST'],
        database=default['DB_NAME'],
        user=default['DB_USER'],
        password= default['DB_PASSWORD']
        )

#executes the query and returns the QEP in json format
def execute_json(connection, query):
    cursor = connection.cursor()
    cursor.execute(query)
    return cursor.fetchall()[0][0][0]['Plan']


#initialise the building of the QEP tree
def buildQEP(query_result_json):
    return Node(query_result_json)


def binary_tree_layout(G, root, width=1.0, height=1.5, horizontal_gap=0.4):
    """ 
    Custom binary tree layout function using depth-first search algorithm.

    Input parameters:
        G: Input tree to be visualized
        root: Root node of the input tree
        width: Width of layout
        height: Height of layout
        horizontal_gap: Horizontal gap between nodes

    Return parameters: 
        pos: Position dictionary for nodes according to depth and order in the tree. 
    """
    pos = {}

    def _dfs(node, depth, min_order, max_order):
        if node.index not in pos:
            pos[node.index] = None

        children = node.children
        if children:
            if len(children) == 1:
                _dfs(children[0], depth + 1, min_order, max_order)
                pos[node.index] = ((min_order + max_order) / 2.0 * width, -depth * height)
            else:
                child_orders = []
                for i, child in enumerate(children):
                    child_min_order = min_order + (max_order - min_order) * i / len(children)
                    child_max_order = min_order + (max_order - min_order) * (i + 1) / len(children)
                    _dfs(child, depth + 1, child_min_order, child_max_order)
                    child_orders.append((child_min_order + child_max_order) / 2.0)

                middle_order = sum(child_orders) / len(child_orders)
                pos[node.index] = (middle_order * width, -depth * height)

                if node.parent and node.parent.parent and len(node.parent.children) == 1 and len(node.parent.parent.children) == 1:
                    parent_middle_order = (min_order + max_order) / 2.0
                    pos[node.index] = (parent_middle_order * width, -depth * height)
        else:
            pos[node.index] = ((min_order + max_order) / 2.0 * width, -depth * height)

            if node.parent and node.parent.parent and len(node.parent.children) == 1 and len(node.parent.parent.children) == 1:
                parent_middle_order = (min_order + max_order) / 2.0
                pos[node.index] = (parent_middle_order * width, -depth * height)

    # increase width based on depth of tree
    def increase_width(root_node, current_depth=0):
        if root_node.children:
            current_depth += 1
            for child in root_node.children:
                increase_width(child, current_depth)
        else:
            nonlocal width
            width = max(width, current_depth * 1.5)

    increase_width(root)
    _dfs(root, 0, 0.0, 1.0)

    for u, v in G.edges():
        x1, y1 = pos[u]
        x2, y2 = pos[v]
        if abs(x1 - x2) > horizontal_gap:
            pos[u] = (x1 + (x2 - x1) * 0.5, y1)

    return pos


def QEP_dfs(root, name):
    """
        Custom implementation for visualizing a QEP.
        
        Input parameters:
            root: Root node of tree structure the models the QEP
            name: String parameter that specifies name of output image

        Return parameters:
            diag_nodes: List of nodes in the graph
            relations: List of relationships between the nodes in the graph
    """
    diag_nodes = []
    relations = []
    node = root
    G = nx.DiGraph()
    
    # Traverse the query and take note of nodes and the relation between each node
    for child in node.children:
        temp_nodes, temp_relations = QEP_dfs(child, name)
        relations.append([node.index, child.index])
        relations.extend(temp_relations)
        diag_nodes.extend(temp_nodes)
    diag_nodes.append([node.node_type, node.index])
    
    # If node is root node start drawing
    if node.parent is None:
        # Sort node base on index
        diag_nodes.sort(key=lambda x: x[1])

        # create graph using networkx
        for label in diag_nodes:
            G.add_node(label[1], label=label[0])
        
        # Create connections based on node relations
        for relation in relations:
            G.add_edge(relation[0], relation[1])

        # set figure size
        plt.figure(figsize=(10, 6))
            
        # draw graph using matplotlib
        pos = binary_tree_layout(G, root, width=1.0, height=1.0) 

        # wrap nodes with rectangles
        for node, coords in pos.items():
            label = G.nodes[node]['label']
            width = np.clip(len(label) * 0.12, 0.35, 2.0)
            rect = mpatches.Rectangle((coords[0] - width / 3, coords[1] - 0.20), width / 1.5, 0.40, facecolor="none", edgecolor="black", linewidth=1, alpha=1)
            plt.gca().add_patch(rect)
      
        for u, v in G.edges():
            x1, y1 = pos[u]
            x2, y2 = pos[v]
            arrow_length = 0.8 
            arrow_start = 0.2  
            dx = x2 - x1
            dy = y2 - y1
            plt.gca().annotate("",
                            xy=(x1 + arrow_length * dx, y1 + arrow_length * dy),
                            xytext=(x1 + arrow_start * dx, y1 + arrow_start * dy),
                            arrowprops=dict(arrowstyle="->", lw=1),
                            )
        
        # adjust label positions
        label_pos = {node: (coords[0], coords[1] - 0.01) for node, coords in pos.items()}
        nx.draw_networkx_labels(G, label_pos, labels={node[1]: node[0] for node in diag_nodes}, font_size=10, font_weight='normal')

        x_coords = [coords[0] for _, coords in pos.items()]
        y_coords = [coords[1] for _, coords in pos.items()]
        x_min, x_max = min(x_coords), max(x_coords)
        y_min, y_max = min(y_coords), max(y_coords)
        padding = 0.7
        plt.xlim(x_min - padding, x_max + padding)
        plt.ylim(y_min - padding, y_max + padding)

        # save figure
        plt.axis("off")
        plt.savefig(f"{name}.png", format="PNG", bbox_inches="tight")
        plt.close()

    return diag_nodes, relations

#printing the QEP with level order traversal
def QEP_bfs(root):
    q = deque()
    cur = root
    q.append(cur)
    currentLevelNodes = 1
    nextLevelNodes = 0

    while(len(q) > 0):
        node = q.popleft()
        currentLevelNodes -= 1
        print(node.node_type,len(node.children),end ="\t")
        for child in node.children:
            q.append(child)
            nextLevelNodes+=1
        if(currentLevelNodes==0):
            print()
            currentLevelNodes = nextLevelNodes
            nextLevelNodes = 0

#parse SQL into a suitable format
def parseSQL(query):
    parsed = sqlparse.parse(query)[1]
    return iterate_parsedSQL(parsed)

#parse SQL into a suitable format
def iterate_parsedSQL(parsed):
    keyword = 'list'
    excluded_keywords = ["and","or","not","between","in","exists", "as"]
    result = {}
    result[keyword] = []
    temp = result[keyword]
    bracket_keyword = None
    for e in parsed.tokens:
        if(not e.is_whitespace and e.value != ","):    
            if(e.is_keyword):
                if(e.value not in excluded_keywords):
                    keyword = e.value
                    result[keyword] = []
                    temp = result[keyword]
                else:
                    temp.append(e.value)
            elif (e.is_group):
                   
                if isinstance(e,sqlparse.sql.Identifier) or isinstance(e,sqlparse.sql.IdentifierList):
                    if(keyword == 'order by'):
                        if isinstance(e,sqlparse.sql.Identifier):
                            temp.append(e.get_name() +" " + ("ASC" if e.get_ordering() == None else e.get_ordering()))
                        else:
                            for item in e.get_identifiers():
                                string = item.get_name() + " " +("ASC" if item.get_ordering() == None else item.get_ordering())
                                temp.append(string)
                    else:
                        sub_result = iterate_parsedSQL(e)
                        temp.extend(sub_result['list'])
                elif isinstance(e,sqlparse.sql.Comparison):
                    is_subquery = False
                    for checkToken in e.tokens:
                        if isinstance(checkToken,sqlparse.sql.Parenthesis):
                            is_subquery = True

                    if not is_subquery:
                        temp.append(e.value)
                    else:
                        for checkToken in e.tokens:
                            if isinstance(checkToken,sqlparse.sql.Parenthesis):
                                sub_result = iterate_parsedSQL(checkToken)
                                if(len(sub_result['list'])> 0):
                                    temp.extend(sub_result['list'])
                                if('select' in sub_result):
                                    temp.append(sub_result)
                                elif('where' in sub_result):
                                    result['where'] = sub_result['where']
                            elif(not checkToken.is_whitespace and checkToken.value != ","):
                                temp.append(checkToken.value)
                elif isinstance(e,sqlparse.sql.Parenthesis) or isinstance(e,sqlparse.sql.Where):
                    sub_result = iterate_parsedSQL(e)
                    if(len(sub_result['list'])> 0):
                        temp.extend(sub_result['list'])
                    if('select' in sub_result):
                        temp.append(sub_result)
                    elif('where' in sub_result):
                        result['where'] = sub_result['where']
                else:
                    temp.append(e.value)
            else:
                if(e.value ==';'):
                    pass
                else:
                    
                    if(e.value == '('):
                        bracket_keyword = keyword
                        temp.append(e.value)
                    elif(e.value == ')'):
                        result[bracket_keyword].append(e.value)
                    else:
                        temp.append(e.value)
    return result

#find difference between sql queries by separating what query 1 has that query 2 does not and vice versa
def query_difference(q1,q2):
    temp_q1={}
    temp_q2={}
    diff_result = {}
    new_subquery_format={}
    final_difference_result={}
    q1_set = set(q1.keys())
    q2_set = set(q2.keys())
    all_keys = q1_set.union(q2_set)
    # check if any key in each query contains a subquery
    for key in all_keys:
        if q1.get(key) is not None and q2.get(key) is not None:
            get_subquery_info(q1,key,temp_q1)
            get_subquery_info(q2,key,temp_q2)
    # retrieve all the keys in Q1 and Q2
    updated_all_keys = set(q1.keys()).union(set(q2.keys()))
    # get all the differences in Q1 and Q2
    for key in updated_all_keys:
        if q1.get(key) is not None and q2.get(key) is not None:
            diff = set(convert_lists_to_tuples(q1[key])).symmetric_difference(set(convert_lists_to_tuples(q2[key])))
            if diff:
                diff_result[key] = list(diff)
        elif q1.get(key) is None:
            diff_result[key]=q2[key]
        else:
            diff_result[key]=q1[key]
    print("Diff_result: ", diff_result)
    print()
    # reformat the diff_result
    for key,value in diff_result.items():
        if 'subquery' in key:
            new_subquery_format[key] = {}
            for subquery in value:
                for tup in subquery:
                    tuple_key = tup[0]
                    tuple_value = list(tup[1])
                    if tuple_key not in new_subquery_format[key]:
                        new_subquery_format[key][tuple_key] = tuple_value
                    else:
                        new_subquery_format[key][tuple_key].extend(tuple_value)
            diff_result[key] = new_subquery_format[key]
    print("New format of diff result is:\n", diff_result)
    print()
    # Using diff_result, we obtain the differences in diff_result and reformat it into final_difference_result
    # With each keyword as key and the values containing a dictionary with Q1 and Q2 as the keys
    for key, value in diff_result.items():
        final_difference_result[key] = {}
        # to handle those keys that have a subquery
        if 'subquery' in key:
            subquery_from_key = key.split('_')[0]
            for subquery_key, subquery_value in diff_result[key].items():
                final_difference_result[key][subquery_key] = {}
                final_difference_result[key][subquery_key]['Q1'] = []
                final_difference_result[key][subquery_key]['Q2'] = []
                if bool(temp_q1):
                    for item in temp_q1[subquery_from_key]:
                        for subitem in item:
                            if subitem[0] == subquery_key:
                                for element1 in diff_result[key][subquery_key]:
                                    for element2 in subitem[1]:
                                        if element1 == element2:
                                            final_difference_result[key][subquery_key]['Q1'].append(element1)
                if bool(temp_q2):
                    for item in temp_q2[subquery_from_key]:
                        for subitem in item:
                            if subitem[0] == subquery_key:
                                for element1 in diff_result[key][subquery_key]:
                                    for element2 in subitem[1]:
                                        if element1 == element2:
                                            final_difference_result[key][subquery_key]['Q2'].append(element1)
        else:
            final_difference_result[key]['Q1'] = []
            final_difference_result[key]['Q2'] = []
            if q1.get(key) is not None:
                for element in value:
                    if element in q1[key]:
                        final_difference_result[key]['Q1'].append(element)
                    else:
                        final_difference_result[key]['Q2'].append(element)
            else:
                for element in value:
                    final_difference_result[key]['Q2'].append(element)
    
    return final_difference_result

# formatting subqueries found in the query
def get_subquery_info(query,key,temp_query):
    for value in query[key]:
        if isinstance(value,dict):
            new_key = '{}_subquery'.format(key)
            new_list = [(key, [value[0]] if len(value)==1 else list(value)) for key, value in value.items()]
            if query.get(new_key) is None:
                query[new_key] = []
                query[new_key].append(new_list)
            if query.get(new_key) is not None:
                if new_list not in query[new_key]:
                    query[new_key].append(new_list)
            query[key].remove(value)
            temp_query[key] = query[new_key]

def convert_lists_to_tuples(obj):
    if isinstance(obj, list) or isinstance(obj, tuple):
        return tuple(convert_lists_to_tuples(item) for item in obj)
    elif isinstance(obj, dict):
        return {key: convert_lists_to_tuples(value) for key, value in obj.items()}
    else:
        return obj

# algo from here onwards
def initialize_index(node, index):
    """Initialize tree with post order numbering index. """
    if not node:
        return None

    # recursively initialize index
    for child in node.children:
        index = initialize_index(child, index)

    node.index = index
    index += 1
    return index

def initialize_node_list(node):
    node_list = []
    if not node:
        return None
    for child in reversed(node.children):
        node_list.extend(initialize_node_list(child))
    node_list.append(node)
    return node_list

#algorithm to find sequence to transform QEP 1 into QEP 2
def tree_edit_distance(tree1, tree2):
    """
    Parameters:
        tree1: Tree to transform
        tree2: Tree to transform into

    Recursion function to determine order of operations to transform tree1 into tree2:
    1. Delete node
    2. Insert node
    3. Update node
    4. Matched node

    The algorithm operates on sub-forests in each recursion.

    Return parameters:
        cost: Minimum tree edit distance
        path: Path taken for minimum tree edit distance
    """
    # if both trees empty, return
    if tree1 is None and tree2 is None:
        return 0, []

    # if tree1 is empty, insert all the nodes of tree2 into tree1
    if tree1 is None:
        path = [["Insert", str(tree2.node_type), str(tree2.index), tree2]]
        for child in tree2.children:
            _, child_path = tree_edit_distance(None, child)
            path.extend(child_path)
        return len(path), path

    # if tree2 is empty, delete all the nodes of tree1
    if tree2 is None:
        path = [["Delete", str(tree1.node_type), str(tree1.index), tree1]]
        for child in tree1.children:
            _, child_path = tree_edit_distance(child, None)
            path.extend(child_path)
        return len(path), path

    # sort children by node_type+index
    tree1.children.sort(key=lambda x: (x.node_type, x.index))
    tree2.children.sort(key=lambda x: (x.node_type, x.index))

    # if the nodes have same index and type, matching nodes
    if tree1.node_type == tree2.node_type:
        cost = 0
        path = [["Matched", str(tree1.node_type), str(tree1.index),"to",str(tree2.node_type),str(tree2.index),tree1,tree2]]
    # update nodes
    else:
        cost = 1
        path = [["Update" , str(tree1.node_type) , str(tree1.index) , "to" , str(tree2.node_type) , str(tree2.index),tree1,tree2]]

    min_cost = float('inf')
    min_path = []

    cost_perm = 0
    path_perm = []

    # calculate edit distance for each pair of corresponding children
    for child1, child2 in zip(tree1.children, tree2.children):
        child_cost, child_path = tree_edit_distance(child1, child2)
        cost_perm += child_cost
        path_perm.extend(child_path)

    # delete extra children in tree1
    for child1 in tree1.children[len(tree2.children):]:
        child_cost, child_path = tree_edit_distance(child1, None)
        cost_perm += child_cost
        path_perm.extend(child_path)

    # insert extra children in tree1
    for child2 in tree2.children[len(tree1.children):]:
        child_cost, child_path = tree_edit_distance(None, child2)
        cost_perm += child_cost
        path_perm.extend(child_path)

    min_cost = cost_perm
    min_path = path_perm

    # add the minimum cost and the corresponding path to the overall cost and path
    cost += min_cost
    path.extend(min_path)
    return cost, path

#returns length and the sequence of changes to transform QEP 1 to QEP 2
def get_path_difference(tree1, tree2):
    initialize_index(tree1, 0)
    initialize_index(tree2, 0)
    qep_diff_length,qep_diff = tree_edit_distance(tree1, tree2)
    qep_diff.reverse()
    return qep_diff_length,qep_diff

#helper function to form a small part of the natural language translation
def form_output_string(diff):
    outputstr_list = []
    if 'Output' in diff.information:
        for output in diff.information['Output']:
            if '.' in output:
                outputstr_list.append(output[output.index('.')+1:])
            else:
                outputstr_list.append(output)
        outputstr = " with output " + str(outputstr_list) + "."
    else:
        outputstr = " with boolean output."
    return outputstr

#returns the list of strings that contains the reasons for the change in QEP in natural language
def diff_to_natural_language(qep_diff,query_diff):
    result = []
    for diff in qep_diff:
        if "Matched" not in diff:
            if "Update" in diff:                
                link = qep_diff_link_to_query_diff(diff[6],query_diff)
                diff_string = diff[6].node_type + form_output_string(diff[6]) + " changed to "+ diff[7].node_type + form_output_string(diff[7])
            elif "Delete" in diff:
                link = qep_diff_link_to_query_diff(diff[3],query_diff)
                diff_string = diff[3].node_type + form_output_string(diff[3]) +  " was removed."
            elif "Insert" in diff:
                link = qep_diff_link_to_query_diff(diff[3],query_diff)
                diff_string = diff[3].node_type + form_output_string(diff[3]) + " was added."
            else:
                print("SHOULD NOT HAPPEN")
            if 'previous' in link:
                diff_string += " The change is possibly influenced by the child nodes where there were relevant changes in the "
                for i in range(len(link['previous'])):
                    diff_string += link['previous'][i].upper()
                    if i != (len(link['previous']) -1):
                        diff_string += ', '
                diff_string += " clauses."
            
            if(diff_string[-8::] == 'clauses.' and len(link) > 1):
                diff_string += " Additionally, there were relevant changes found in the following clauses."
            elif diff_string[-8::] != 'clauses.' and len(link) > 0:
                diff_string += " This is due to changes in the following clauses."
            result.append(diff_to_natural_language_recursion(diff,diff_string,link))

        else:
            # print(diff[6].node_type + " with output " + str(diff[6].information['Output']) + " matched "+ diff[7].node_type + " with output " + str(diff[7].information['Output']))
            # print("\n")
            for child in diff[6].children:
                for reason in child.reasons:
                    if reason not in diff[6].reasons:
                        diff[6].reasons.append(reason)
    return result

#return a string that contains the differences in natural langauge for a particular node change in QEP 1 to transform into QEP 2
def diff_to_natural_language_recursion(diff,diff_string,link):
    for key, value in link.items():
        if key != 'previous' and key !='list':
            if 'subquery' not in key:
                diff_string += " In the " + key.upper() + " clause, "
                if len(value['Q1'])> 0:
                    diff_string += "query 1 had "
                    for q1_diff in value['Q1']:
                        if q1_diff != '(' and q1_diff != ')':
                            diff_string += q1_diff + ", "
                    diff_string += "while query 2 did not"
                else:
                    diff_string += "query 1 did not have relevant differences that query 2 did not have"
                if len(value['Q2'])> 0:
                    diff_string += " and query 2 had "
                    for q2_diff in value['Q2']:
                        if q2_diff != '(' and q2_diff != ')':
                            diff_string += q2_diff + ", "
                    diff_string += "while query 1 did not"
                diff_string += '.'
            else:
                diff_string += " In the " + key.upper()[:key.index('_')] + " clause, there is also a subquery. The relevant differences in the subquery are as follows:\n"
                # print("partial diff string", diff_string)
                diff_string = diff_to_natural_language_recursion(diff,diff_string,value)
                diff_string += "\nThis concludes the differences in the subquery."
    return diff_string


#finds relevant links/reasons as to why there is a node change in QEP 1 to transform into QEP 2
#this is based on either the current node's child nodes which had differences
#or the current node's output changes in QEP 1 as compared to query differences
def qep_diff_link_to_query_diff(diff,query_diff):
    result = {}
    if diff.node_type == "Sort":
        #check for order by differences
        if 'order by' in query_diff:
            result['order by'] = query_diff['order by']
        
    if diff.node_type == "Aggregate" or diff.node_type == "Group":
        aggregation_list = ['count','sum','avg','min','max','array_agg','string_agg','group_concat','rank','dense_rank','row_number']
        #check for select and group by differences
        if 'select' in query_diff:
            for q, differences in query_diff['select'].items():
                for difference in differences:
                    for aggregation in aggregation_list:
                        aggregation += '('
                        if aggregation in difference:
                            if 'select' not in result:
                                result['select'] = {'Q1':[],'Q2':[]}
                                diff.reasons.append('select')
                            if difference not in result['select'][q]:
                                result['select'][q].append(difference)
        if 'group by' in query_diff:                
            for q, differences in query_diff['group by'].items():
                for difference in differences:
                    for attribute in diff.information['Output']:
                        if '.' in attribute:
                            filtered = attribute[attribute.index('.')+1:]
                        else: 
                            filtered = attribute
                        if filtered in difference:
                            if 'group by' not in result:
                                result['group by'] = {'Q1':[],'Q2':[]}
                                diff.reasons.append('group by')
                            if difference not in result['group by'][q]:
                                result['group by'][q].append(difference)
    #find reasons in child nodes         
    if len(diff.children) !=0:
        for child in diff.children:
            if len(child.reasons)>0:
                if 'previous' not in result:
                    result['previous'] = []
                for reason in child.reasons:
                    if reason not in diff.reasons:
                        diff.reasons.append(reason)
                    if reason not in result['previous']:
                        result['previous'].append(reason)

    #find reasons from current node's output changes in QEP 1 as compared to query differences
    if 'previous' not in result:
        for keyword, differences_q1q2_dict in query_diff.items():
            if 'list' != keyword:
                if 'subquery' not in keyword:
                    if 'Output' in diff.information:
                        for attribute1 in diff.information['Output']:
                            if '.' in attribute1:
                                filtered = attribute1[attribute1.index('.')+1:]
                            else: 
                                filtered = attribute1
                            for attribute2 in differences_q1q2_dict['Q1']:
                                if filtered in attribute2:
                                    if keyword not in result:
                                        result[keyword] = {'Q1':[],'Q2':[]}
                                        diff.reasons.append(keyword)
                                    if attribute2 not in result[keyword]['Q1']:
                                        result[keyword]['Q1'].append(attribute2)

                            for attribute2 in differences_q1q2_dict['Q2']:
                                if filtered in attribute2:
                                    if keyword not in result:
                                        result[keyword] = {'Q1':[],'Q2':[]}
                                        diff.reasons.append(keyword)
                                    if attribute2 not in result[keyword]['Q2']:
                                        result[keyword]['Q2'].append(attribute2)
                    else:
                        unique_attributes = ["not","exists","in"]
                        for key in differences_q1q2_dict:
                            for attribute in differences_q1q2_dict[key]:
                                if attribute in unique_attributes:
                                    if keyword not in result:
                                        result[keyword] = {'Q1':[],'Q2':[]}
                                        diff.reasons.append(keyword)
                                    if attribute not in result[keyword][key]:
                                        result[keyword][key].append(attribute)         
                else:
                    result[keyword] = differences_q1q2_dict
    return result  


#returns a list of strings that tells the natural language difference between the 2 queries
def sql_diff_to_natural_language(query_diff):
    result = []          
    for keyword,value_dict in query_diff.items():
        if keyword != 'list':
            if 'subquery' not in keyword:
                diff_string = "For the " + keyword.upper() + " clause, "
                for key,value in value_dict.items():
                    if len(value)>0:
                        diff_string_partial = ""
                        for item in value:
                            if item != 'as' and item != '(' and item != ')':
                                diff_string_partial += item + ", "
                        if key == 'Q1':
                            diff_string = diff_string + "query 1 included " + diff_string_partial + "while query 2 did not."
                        else:
                            diff_string = diff_string + "query 2 included " + diff_string_partial + "while query 1 did not."
                result.append(diff_string)
            else:
                diff_string = "For the nested subquery in the " + keyword[:keyword.index('_')].upper() + " clause , the differences are as follows:"
                result.append(diff_string)
                result.extend(sql_diff_to_natural_language(value_dict))
                result.append("This concludes the differences in the subquery.")
        
    return result

def convert_to_text(x):
    text = ''
    for line in x:
        text += line + '\n\n'
    return text

