from functools import cmp_to_key
import math
import random
import itertools
import re
import base64
import json
import pickle
import sys
import os
import glob

import sublime
import sublime_plugin
import ctypes
import webbrowser
import zlib
import subprocess

from io import StringIO

try:
	import urlparse
	from urllib import urlencode
except: # For Python 3
	import urllib.parse as urlparse
	from urllib.parse import urlencode


g_paths = None
g_paths_db = os.path.join(os.path.split(__file__)[0],"toolpaths")
try:
	g_paths = open(g_paths_db,"r")
except:
	g_paths = None
	pass

if(g_paths != None):
	f = g_paths
	g_paths = json.load(f)
	f.close()
else:
	g_paths = {
		"SFT" : ""
	}

print(g_paths)

def save_paths():
	global g_paths
	global g_paths_db
	with open(g_paths_db, 'w') as outfile:
		json.dump(g_paths, outfile)

def _run_system_command(call_cmd):
	p = subprocess.Popen(call_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	stdout, stderr = p.communicate()
	if stderr:
		print(stderr)

def _open_browser_with_url(url):
	browser_executable = None

	if sys.platform == "win32":
		#browser_executable = 'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe %s'
		browser_executable = 'C:/Program Files/Mozilla Firefox/firefox.exe %s'
	if sys.platform == "darwin":
		# MacOS
		browser_executable = 'open -a /Applications/Google\ Chrome.app %s'

	# Linux
	# browser_executable = '/usr/bin/google-chrome %s'

	if browser_executable != None:
		webbrowser.get(browser_executable).open(url)

def _open_local_sft(abs_path_to_file):
	global g_paths
	DETACHED_PROCESS = 0x00000008
	pid = subprocess.Popen([g_paths["SFT"], "-i", abs_path_to_file], creationflags=DETACHED_PROCESS).pid
	print("created process with pid: " + str(pid))


def _create_cpp_doc_url(search_symbol):
	url = "https://en.cppreference.com/mwiki/index.php?"
	params = {'title': 'Special:Search', 'search': search_symbol}

	url_parts = list(urlparse.urlparse(url))
	query = dict(urlparse.parse_qsl(url_parts[4]))
	query.update(params)

	url_parts[4] = urlencode(query)

	return urlparse.urlunparse(url_parts)

def _create_search_query(query_string):
	#google
	#url = 'http://www.google.com/search?ie=UTF-8&oe=UTF-8&sourceid=navclient&gfns=1&q=X'
	#params = {'sourceid': 'navclient', 'q': query_string, 'oe': 'UTF-8', 'ie': 'UTF-8', 'gfns': '1'}
	#duckduckgo
	url = "https://duckduckgo.com/?q=X&ia=web"
	params = {'ia': 'web', 'q': query_string}

	url_parts = list(urlparse.urlparse(url))
	query = dict(urlparse.parse_qsl(url_parts[4]))
	query.update(params)
	url_parts[4] = urlencode(query)
	return urlparse.urlunparse(url_parts)

##################################################################################################################################
##################################################################################################################################
##################################################################################################################################

class PrimitiveFunctions(object):

	sep = "//--------------------------------------------------------------------------------------------------------------------------------"
	sp  = "/*                                                                                                                              */"

	def password(length, charset = None):
		if(charset != None):
			return ''.join(random.choice(charset) for _ in range(length))
		else:
			pwdchrs = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
			return ''.join(random.choice(pwdchrs) for _ in range(length))

	def platform():
		return sys.platform
	def version():
		return sys.version
	def edit():
		sublime.active_window().open_file(__file__)
		return ""

	def path():
		global g_paths
		return str(g_paths)

	def set(K,V):
		global g_paths
		if K in g_paths:
			g_paths[K] = V
			save_paths()
			return str(g_paths)

		return None

	def hash32(strvalue):
		h = ctypes.c_uint(2166136261)
		for c in strvalue:
			h.value = h.value ^ ctypes.c_uint(ord(c)).value
			h.value = h.value * ctypes.c_uint(16777619).value
		return str(h.value)

	def env(env_var = None): #print enviroment variables
		if(env_var == None):
			return json.dumps(dict(os.environ), sort_keys=True, indent=4)
		else:
			return os.environ[env_var]

	def glob(abs_path): #list items at path
		result = []
		for r, d, f in os.walk(abs_path):
			for folder in d:
				result.append(os.path.join(r,folder))
			for file in f:
				result.append(os.path.join(r,file))
		return ";".join(result)

	def ls(abs_path): #list items at path
		result = []
		for f in os.listdir(abs_path):
			result.append(os.path.join(abs_path,f))
		return ";".join(result)

	def find(search_path, filename):
		result = []
		fl = filename.lower()
		for r, d, f in os.walk(search_path):
			for file in f:
				if fl in file.lower():
					result.append(os.path.join(r,file))
		if result:
			return ";".join(result)
		else:
			return filename


class CalculateScope(object):
	def __init__(self):
		self.dict = {}

		self.load_commands()
		self.load_shortcuts()

	def load_commands(self):

		#inherit from default functions
		for key in dir(random):
			self.dict[key] = getattr(random, key)
		for key in dir(math):
			self.dict[key] = getattr(math, key)

		for key in dir(itertools):
			self.dict[key] = getattr(itertools, key)

		help_functions = []
		for key in dir(PrimitiveFunctions):
			if(key.startswith("__")):
				continue
			if(key.endswith("__")):
				continue
			tmp = getattr(PrimitiveFunctions, key)
			help_functions.append(key)
			self.dict[key] = tmp

		self.dict['help'] = lambda: help_functions

	def load_shortcuts(self):
		self.dict['pwd'] = self.dict['password']


	def start(self):
		self.dict['i'] = 0

	def next(self):
		self.dict['i'] = self.dict['i'] + 1

	def evaluate_str(self, expr):
		result = eval(expr, self.dict)
		if not isinstance(result, str):
			result = str(result)
		return result


class CalculateCommand(sublime_plugin.TextCommand):
	def __init__(self, *args, **kwargs):
		sublime_plugin.TextCommand.__init__(self, *args, **kwargs)

		self.calc_context = CalculateScope()

	def run(self, edit, **kwargs):
		self.calc_context.start()

		errors = []
		for region in self.view.sel():
			try:
				error = self.run_one_selection(edit, region)
			except Exception as exception:
				error = str(exception)

			self.calc_context.next()

			if error:
				errors.append(error)
				self.view.replace(edit, region, error)

		if(len(errors) > 0):
			sublime.status_message(";".join(errors))

	def run_one_selection(self, edit, region):
		if not region.empty():
			formula = self.view.substr(region)
			value = self.calc_context.evaluate_str(formula)
			self.view.replace(edit, region, value)

##################################################################################################################################

class ViewdocumentationCommand(sublime_plugin.TextCommand):
	def __init__(self, *args, **kwargs):
		sublime_plugin.TextCommand.__init__(self, *args, **kwargs)

	def run(self, edit, **kwargs):
		errors = []
		for region in self.view.sel():
			try:
				error = self.run_one_selection(edit, region)
			except Exception as exception:
				error = str(exception)

			if error:
				errors.append(error)

		if(len(errors) > 0):
			sublime.status_message(";".join(errors))

	def run_one_selection(self, edit, region):
		if not region.empty():
			value = self.view.substr(region)
			_open_browser_with_url(_create_cpp_doc_url(value))

##################################################################################################################################

class SmarterGotoCommand(sublime_plugin.TextCommand):
	def __init__(self, *args, **kwargs):
		sublime_plugin.TextCommand.__init__(self, *args, **kwargs)

		self.urlregex = re.compile(
			r'^(?:http|ftp)s?://' # http:// or https://
			r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|' #domain...
			r'localhost|' #localhost...
			r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})' # ...or ip
			r'(?::\d+)?' # optional port
			r'(?:/?|[/?]\S+)$', re.IGNORECASE)

		self.urlregex2 = re.compile(
			r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|' #domain...
			r'localhost|' #localhost...
			r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})' # ...or ip
			r'(?::\d+)?' # optional port
			r'(?:/?|[/?]\S+)$', re.IGNORECASE)


	def run(self, edit, **kwargs):
		errors = []
		for region in self.view.sel():
			try:
				error = self.run_one_selection(edit, region)
			except Exception as exception:
				error = str(exception)

			if error:
				errors.append(error)

		if(len(errors) > 0):
			sublime.status_message(";".join(errors))

	def _find_and_goto(self,value):
		clean_value = value.replace("\n","")

		if re.match(self.urlregex, value) is not None:
			#url
			_open_browser_with_url(value)
			return True

		elif re.match(self.urlregex2, value) is not None:
			#url
			_open_browser_with_url(value)
			return True

		elif os.path.isfile(clean_value):
			#file
			sublime.active_window().open_file(clean_value)
			return True

		elif os.path.isdir(clean_value):
			#directory
			if sys.platform == "win32":
				_run_system_command(["explorer", os.path.normpath(clean_value)])
			if sys.platform == "darwin":
				_run_system_command(["open", os.path.normpath(clean_value)])

			return True

		return False

	def run_one_selection(self, edit, region):
		current_file = self.view.file_name()

		file_md = current_file != None and current_file.lower().endswith(".md")
		file_sft = current_file != None and current_file.lower().endswith(".sft") 

		##google lucky query
		#_open_browser_with_url(_create_search_query(value))

		#do domething with current file if possible


		if not region.empty():
			#we have selection

			value = self.view.substr(region)
			if self._find_and_goto(value) == True:
				return

		if file_md:
			_open_browser_with_url(current_file)
			return
		elif file_sft:
			_open_local_sft(current_file)
			return
		else:
			self._find_and_goto(sublime.get_clipboard());
			return

##################################################################################################################################

class TogglePathFormatCommand(sublime_plugin.TextCommand):
	def __init__(self, *args, **kwargs):
		sublime_plugin.TextCommand.__init__(self, *args, **kwargs)

	def run(self, edit, **kwargs):
		errors = []
		for region in self.view.sel():
			try:
				error = self.run_one_selection(edit, region)
			except Exception as exception:
				error = str(exception)

			if error:
				errors.append(error)

		if(len(errors) > 0):
			sublime.status_message(";".join(errors))

	def _update_string(self,value):

		twinstr = value.count("\\\\")
		if twinstr != 0:
			return value.replace("\\\\","\\")

		t0 = value.count("\\")
		t1 = value.count("/")

		if t0 != 0 and t1 != 0:
			if t0 > t1:
				return value.replace("/","\\")
			else:
				return value.replace("\\","/")
		elif t0 != 0:
			return value.replace("\\","/")
		else:
			return value.replace("/","\\\\")
		return value

	def run_one_selection(self, edit, region):
		if not region.empty():
			value = self.view.substr(region)
			new_value = self._update_string(value)
			if new_value != value:
				self.view.replace(edit, region, new_value)

##################################################################################################################################

class ToggleNewlineSplitCommand(sublime_plugin.TextCommand):
	def __init__(self, *args, **kwargs):
		sublime_plugin.TextCommand.__init__(self, *args, **kwargs)

	def run(self, edit, **kwargs):
		errors = []
		for region in self.view.sel():
			try:
				error = self.run_one_selection(edit, region)
			except Exception as exception:
				error = str(exception)

			if error:
				errors.append(error)

		if(len(errors) > 0):
			sublime.status_message(";".join(errors))

	def _update_string(self,value):

		separators = value.count(";")
		if separators != 0:
			return value.replace(";","\n")

		newlines = value.count("\n")
		if newlines != 0:
			return value.replace("\n",";")

		return value

	def run_one_selection(self, edit, region):
		if not region.empty():
			value = self.view.substr(region)
			new_value = self._update_string(value)
			if new_value != value:
				self.view.replace(edit, region, new_value)


##################################################################################################################################

class MaximizeWindowCommand(sublime_plugin.TextCommand):
	def __init__(self, *args, **kwargs):
		sublime_plugin.TextCommand.__init__(self, *args, **kwargs)

	def run(self, edit, **kwargs):
		# https://docs.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-showwindowasync
		hwndSublime = ctypes.windll.user32.FindWindowA(b'PX_WINDOW_CLASS', None)
		ctypes.windll.user32.ShowWindowAsync(hwndSublime, 3)

##################################################################################################################################
##################################################################################################################################
##################################################################################################################################
##################################################################################################################################

class bucket():
	def __init__(self, distance, prev_bucket):
		self.str = ""
		self.hasTab = False
		self.distance = distance
		self.next = prev_bucket

	def find(self,distance):
		itr = self
		while itr != None:
			if itr.distance == distance:
				return itr
			itr = itr.next
		return itr

	def next_length(self):
		itr = self.next
		result = 0
		while itr != None:
			result = result + len(itr.str)
			if itr.hasTab:
				result = result + 1
			itr = itr.next
		return result

	def calculate_distance(self, distance, tab_size):
		index = distance // tab_size

		nd = self.find(index)

		if(nd == None):
			if len(self.str) < tab_size:
				if self.hasTab:
					self.hasTab = False
				self.str = self.str + " " * (tab_size - len(self.str))

			max_len = (self.distance + 1) * tab_size
			count = distance - max_len
			self.str = self.str + " " * count
			return self.next_length() + len(self.str)
		else:
			localIndex = distance - nd.distance * tab_size

			if localIndex == 0:
				return nd.next_length()

			if localIndex > len(nd.str):
				nd.str = nd.str + " " * (localIndex - len(nd.str))

			return nd.next_length() + localIndex

	def rebuild(self):
		itr = self
		result = ""
		while itr != None:
			if itr.hasTab:
				result = itr.str + "\t" + result
			else:
				result = itr.str + result
			itr = itr.next
		return result

	def create_node(self):
		return bucket(self.distance + 1, self)

	def append(self,c,tab_size):
		if c == "\t":
			self.hasTab = True
			return self.create_node()

		self.str = self.str + c
		if len(self.str) < tab_size:
			return self
		else:
			return self.create_node()

class PunchCursorCommand(sublime_plugin.TextCommand):

	def cut_string_to_distance(current_string, expected_distance, tab_size):
		split_line = string_value.split("\t")
		distance = 0
		itr = 0
		for i in split_line:
			next_distance = (distance + len(i))
			if next_distance >= expected_distance:
				return itr + next_distance - expected_distance
			else:
				itr = itr + len(i)
				distance = next_distance

			if (distance + tab_size) > expected_distance:
				return itr
			else:
				distance = distance + tab_size
				itr = itr + 1
		return itr

	def run(self, edit, **kwargs):

		#copy existing selection so we don't mess with it
		current_selections = list(self.view.sel())

		tab_size = 4

		if kwargs['down'] == False:
			current_selections = reversed(current_selections)

		for region in current_selections:
			if not region.empty():
				continue

			#cursor position
			row, col = self.view.rowcol(region.end())

			line_start = self.view.text_point(row, 0)
			line_col = self.view.text_point(row, col)

			#make region with line start and current cursor position
			start_line_to_cursor = sublime.Region(line_start,region.end())

			start_line_to_cursor_value = self.view.substr(start_line_to_cursor)
			cursor_tab_count = start_line_to_cursor_value.count('\t')
			cursor_length = len(start_line_to_cursor_value)
			cursor_distance = cursor_length + cursor_tab_count * (tab_size - 1)

			#move to next line up or down
			if kwargs['down'] == True:
				row = row + 1
			else:
				row = row - 1

			next_line_start_point = self.view.text_point(row, 0)
			next_line_region = self.view.full_line(next_line_start_point)

			next_line_content = self.view.substr(next_line_region).replace("\n","")

			head_bucket = bucket(0,None)

			#break line to evaluate cursor position on next line
			for c in next_line_content:
				head_bucket = head_bucket.append(c,tab_size)

			#calculate line length
			distance = head_bucket.calculate_distance(cursor_distance,tab_size)
			altered_content = head_bucket.rebuild()
			if altered_content != next_line_content:
				#line can change in some cases
				self.view.replace(edit, next_line_region, altered_content + "\n")
			self.view.sel().add(sublime.Region(next_line_region.begin() + distance,next_line_region.begin() + distance))
