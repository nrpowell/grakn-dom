from argparse import ArgumentParser
from grakn.client import Graph
from html.parser import HTMLParser
from subprocess import check_output
import hashlib
import re
import requests

""" Grakn path """
_GRAQL_PATH = "/usr/local/Cellar/grakn/0.16.0/bin/graql.sh" 

""" Global paths to relevant files """
_SCHEMA_PATH = "domSchema.gql"
_RULESET_PATH = "domRules.gql"



########################################################################################################################
######################################################################################################################## 
""" ENCODE """
######################################################################################################################## 
########################################################################################################################

""" Class definition for the Dom tree to keep track of the document's structure """
class DomTree(object):
	def __init__(self, unique_id):
		self._ID = unique_id
		self._left = None
		self._right = None
		self._parent = None
		self._children = []

	@property
	def children(self):
		return self._children

	@property
	def parent(self):
		return self._parent

	@property
	def left(self):
		return self._left

	@property
	def right(self):
		return self._right

	@property
	def ID(self):
		return self._ID

	@children.setter
	def add_child(self, child):
		self._children.append(child)

	@parent.setter
	def parent(self, parent):
		self._parent = parent

	@left.setter
	def left(self, left):
		self._left = left

	@right.setter
	def right(self, right):
		self._right = right

	@ID.setter
	def ID(self, ID):
		self._ID = ID



class GraknHTMLParser(HTMLParser):

	def __init__(self, graph):
		self.current_node = DomTree("\"" + graph.execute("insert $x isa root;")[0]['x']['id'] + "\"")
		self.current_query = ""
		self.graph = graph

		""" Required by the overriden init """
		self.convert_charrefs = True
		self.reset()

	def handle_decl(self, decl):
		pass

	def add_node_to_tree(self):
		new_node = DomTree("")
		new_parent = self.current_node
		new_left = None
		if new_parent:
			if new_parent.children:
				new_left = new_parent.children[-1]
			new_parent.add_child = new_node

		if new_left:
			new_left.right = new_node
		
		new_node.parent = new_parent
		new_node.left = new_left
		self.current_node = new_node

	""" Function to insert the entity and relation into Grakn"""
	def execute_grakn_query(self, grakn_query):
		#print(grakn_query)
		grakn_response = self.graph.execute(grakn_query.encode('utf8'))
		node_id = "\"" + grakn_response[0]['x']['id'] + "\""
		if self.current_node.parent:
			grakn_relation_query = "match $x id " + node_id + "; $y id " + self.current_node.parent.ID + "; "
			if self.current_node.left:
				grakn_relation_query += "$z id " + self.current_node.left.ID + "; insert (left-sibling: $z, right-sibling: $x) isa horizontal; "
			else:
				grakn_relation_query += "insert "

			grakn_relation_query += "(parent: $y, child: $x) isa vertical;"
			self.graph.execute(grakn_relation_query.encode('utf8'))

		self.current_node.ID = node_id


	def handle_starttag(self, tag, attrs):
		#print("Start tag is: " + tag)
		object = "container"
		attr_list = []

		if re.search("h[1-6]", tag) is not None:
			object = "h"
			attrs.append(('hsize', tag[1]))			
		elif tag in default_tags:
			object = tag
			attr_list = default_tags[tag] + default_tags['global']
		else:
			""" These are objects under the container entity class """
			tag = "\"" + tag + "\""
			object += " has tag " + tag

		grakn_query = "insert $x isa " + object
		non_default_attrs = ""
		for attr in attrs:
			if attr[0] in attr_list:
				resource = attr[0]
				value = attr[1]

				if resource == "id":
					resource = "unique-id"

				if resource not in non_string_resources:
					value = "\"" + value.replace('"', '\'') + "\""

				grakn_query += ", has " + resource + " " + value
			else:
				""" Sometimes attributes come in with a value of 'None' """
				if attr[1] == None:
					if attr[0] != "\"":
						non_default_attrs += attr[0] + " |::| "
				else:
					content = "\\\"" + attr[1].replace('"', '\'') + "\\\""
					non_default_attrs += attr[0] + "= " + content + " |::| "
			## This is for non-default tag attributes, which are lumped into the 'other' field under the global entity

		if non_default_attrs:
			non_default_attrs = "\"" + non_default_attrs + "\""
			grakn_query += ", has other " + non_default_attrs

		grakn_query += ";"
		self.add_node_to_tree()
		self.execute_grakn_query(grakn_query)


	def handle_endtag(self, tag):
		self.current_node = self.current_node.parent

	def handle_data(self, data):
		if data.strip():
			if data == "\\":
				data = "\"" + "\\" + data + "\""
			else:
				data = "\"" + data.replace('"', '\'') + "\""

			grakn_query = "insert $x isa data has body " + data + ";"

			self.add_node_to_tree()
			self.execute_grakn_query(grakn_query)

			""" This line distinguishes data nodes from tag nodes, because data nodes cannot be parents of anything """
			self.current_node = self.current_node.parent

	def handle_comment(self, data):
		pass

non_string_resources = {'tabindex', 'disabled', 'hsize', 'height', 'width', 'ismap', 'value', 'start'}

default_tags = {
	'global'	: ['class', 'id', 'style', 'title', 'tabindex', 'other'],
	'a'			: ['href', 'rel', 'type'],
	'blockquote': ['cite'],
	'b'			: [],
	'button'	: ['disabled', 'name', 'type', 'value'],
	'div'		: [],
	'h'			: ['hsize'],
	'hr'		: [],
	'html'		: [],
	'iframe'	: ['height', 'name', 'sandbox', 'src', 'width'],
	'img'		: ['alt', 'height', 'ismap', 'src', 'usemap', 'width'],
	'i'			: [],
	'li'		: ['value'],
	'link'		: ['href', 'rel', 'type'],
	'ol'		: ['start', 'type'],
	'nav'		: [],
	'p'			: [],
	'script'	: ['src', 'type'],
	'ul'		: []
}


def insert_schema(url_hash, graph):
	data = ""
	with open(_SCHEMA_PATH, "r") as schema:
		data = schema.read().replace('\n', ' ')
	
	graph.execute(data)

def hash_url(url):
	hash_url = url.encode('utf-8')
	hash_obj = hashlib.sha1(hash_url)
	return hash_obj.hexdigest()

def encode(url):
	""" Convert provided URL into hash string """
	url_hash = hash_url(url)
	print('Unique hash of the provided URL is: ' + str(url_hash))

	""" Initialize Grakn graph and insert ontology """
	graph = Graph(uri='http://localhost:4567', keyspace=url_hash)

	""" Delete any values potentially already in the keyspace """
	# graph.execute("match $x isa entity; delete $x;")
	# graph.execute("match $x isa resource; delete $x;")

	insert_schema(url_hash, graph)

	""" Feeds the HTML response into the parser """
	parser = GraknHTMLParser(graph)
	response = requests.get(url)
	parser.feed(str(response.text))
	print("Finished encoding document\n")


########################################################################################################################
######################################################################################################################## 
""" DECODE """
######################################################################################################################## 
########################################################################################################################

""" Global variable where the Grakn graph instance will be stored """
graph = None

def grakn_attributes(possible_attrs, ID, tag):
	global graph
	tag_attr_string = ""
	if tag in default_tags:
		tag_attr_string += "<" + tag

	for attr in possible_attrs:
		grakn_attr = attr
		if attr == 'id':
			grakn_attr = 'unique-id'

		grakn_response = graph.execute("match $x id " + ID + " has " + grakn_attr + " $val; select $val;")

		for param in grakn_response:
			""" Gets the Grakn value of the tag """
			value = param['val']['value']

			""" If an attr=='tag', must be of type container and has 2 resources - the real html tag, and any other elements """
			""" If an attr=='body', must be of type data and contains only a body, so we return """
			""" If an attr=='other', takes the concatenated string of all extra html elements and re-inserts them correctly """
			""" Otherwise the tag plays an entity sub-typed from global; easy to deal with """
			if attr == 'tag':
				tag_attr_string = "<" + value
			elif attr == 'body':
				tag_attr_string = value
				return tag_attr_string
			elif attr == 'other':
				value = value.split("|::|")
				for v in value:
					tag_attr_string += " " + v

			else:
				tag_attr_string += " " + attr + "="
				if attr not in non_string_resources:
					value = "\"" + value + "\""
				tag_attr_string += str(value)

	tag_attr_string += ">"
	return tag_attr_string


def construct_tag_attributes(ID, tag):
	possible_attrs = []
	if tag == 'data':
		possible_attrs = ['body']
	elif tag == 'container':
		possible_attrs = ['tag', 'other']
	elif tag in default_tags:
		possible_attrs = default_tags['global'] + default_tags[tag]
	else:
		print("Error: shouldn't happen")
		return ""

	return grakn_attributes(possible_attrs, ID, tag)
	

""" Searches the Grakn knowledge base recursively and reconstructs the HTML document from it"""
def construct_dom_recursive(parent_ID):
	global graph
	children_response = graph.execute("match $x id " + parent_ID + "; (parent: $x, child: $y) isa vertical; select $y;")

	""" String representing the html contents of this level of the dom tree """
	level_string = ""

	""" ID of the leftmost (first) child """
	leftmost = ""

	for child in children_response:
		tag_ID = "\"" + child['y']['id'] + "\""
		if not graph.execute("match $x id " + tag_ID + "; (left-sibling: $y, right-sibling: $x) isa horizontal; select $y;"):
			leftmost = tag_ID
			break

	""" Leftmost is condition so that we skip the while loop if there are no children """
	while leftmost:
		tag = graph.execute("match $x id " + leftmost + "; select $x;")[0]['x']['isa']
		tag_attributes = construct_tag_attributes(leftmost, tag)
		level_string += tag_attributes

		level_string += construct_dom_recursive(leftmost)

		if tag != "data":
			end_idx = tag_attributes.find(" ")

			""" Determines actual tag name from the constructed string """
			spec_tag = tag_attributes[1:end_idx]
			level_string += "</" + spec_tag + ">"

		next_node = graph.execute("match $x id " + leftmost + "; (left-sibling: $x, right-sibling: $y) isa horizontal; select $y;")

		if next_node:
			next_node_ID = next_node[0]['y']['id']
			leftmost = "\"" + next_node_ID + "\""
		else:
			leftmost = ""

	return level_string



def decode(my_keyspace):
	global graph
	graph = Graph(uri='http://localhost:4567', keyspace=my_keyspace)

	""" If a keyspace is uninitialized, it will return 8 """
	does_exist = True if graph.execute("match $x; aggregate count;") > 8 else False

	if does_exist:
		root_node = graph.execute("match $x isa root; select $x;")[0]['x']
		root_node_ID = "\"" + root_node['id'] + "\""
		html_string = construct_dom_recursive(root_node_ID)
		f = open(my_keyspace + ".html", 'w')
		f.write(html_string)
		f.close()

	else:
		print("Keyspace does not exist! Make sure you have typed the hash properly. ")


if __name__=="__main__":
	parser = ArgumentParser(
		description="Encode or decode between a DOM and a Grakn knowledge base")
	parser.add_argument("-e", "--encode", help="The document (usually web page) to encode in Grakn")
	parser.add_argument("-d", "--decode", help="The Grakn keyspace (as checksum) to convert into HTML format")
	sysargs = parser.parse_args()

	if sysargs.encode:
		encode(sysargs.encode)
	if sysargs.decode:
		decode(sysargs.decode)