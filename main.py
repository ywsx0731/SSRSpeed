#coding:utf-8

import time
import sys
import os
import json
import _thread
import platform
from optparse import OptionParser
import logging

from SSRSpeed.Shadowsocks.Shadowsocks import Shadowsocks as SSClient
from SSRSpeed.Shadowsocks.ShadowsocksR import ShadowsocksR as SSRClient
from SSRSpeed.Shadowsocks.V2Ray import V2Ray as V2RayClient
from SSRSpeed.SpeedTest.speedTest import SpeedTest
from SSRSpeed.Result.exportResult import ExportResult
import SSRSpeed.Result.importResult as importResult
from SSRSpeed.Utils.checkPlatform import checkPlatform
from SSRSpeed.Utils.ConfigParser.ShadowsocksParser import ShadowsocksParser as SSParser
from SSRSpeed.Utils.ConfigParser.ShadowsocksRParser import ShadowsocksRParser as SSRParser
from SSRSpeed.Utils.ConfigParser.V2RayParser import V2RayParser
from SSRSpeed.Utils.checkRequirements import checkShadowsocks

from config import config

if (not os.path.exists("./logs/")):
	os.mkdir("./logs/")
if (not os.path.exists("./results/")):
	os.mkdir("./results/")

loggerList = []
loggerSub = logging.getLogger("Sub")
logger = logging.getLogger(__name__)
loggerList.append(loggerSub)
loggerList.append(logger)

formatter = logging.Formatter("[%(asctime)s][%(levelname)s][%(thread)d][%(filename)s:%(lineno)d]%(message)s")
fileHandler = logging.FileHandler("./logs/" + time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime()) + ".log",encoding="utf-8")
fileHandler.setFormatter(formatter)
consoleHandler = logging.StreamHandler()
consoleHandler.setFormatter(formatter)

VERSION = "2.3.0-alpha"

def setArgsListCallback(option,opt_str,value,parser):
	assert value is None
	value = []
	def floatable(arg):
		try:
			float(arg)
			return True
		except ValueError:
			return False
	for arg in parser.rargs:
		if (arg[:2] == "--" and len(arg) > 2):
			break
		if (arg[:1] == "-" and len(arg) > 1 and not floatable(arg)):
			break
		if (arg.replace(" ","") == ""):
			continue
		value.append(arg)
#	print(parser.values)
#	print(option.dest)
#	print(opt_str)
	del parser.rargs[:len(value)]
	setattr(parser.values,option.dest,value)
#	print(value)

def setOpts(parser):
	parser.add_option(
		"-c","--config",
		action="store",
		dest="guiConfig",
		default="",
		help="Load config generated by shadowsocksr-csharp."
		)
	parser.add_option(
		"-u","--url",
		action="store",
		dest="url",
		default="",
		help="Load ssr config from subscription url."
		)
	parser.add_option(
		"-m","--method",
		action="store",
		dest="test_method",
		default="socket",
		help="Select test method in [speedtestnet,fast,socket]."
		)
	parser.add_option(
		"-M","--mode",
		action="store",
		dest="test_mode",
		default="all",
		help="Select test mode in [all,pingonly]."
		)
	parser.add_option(
		"--include",
		action="callback",
		callback = setArgsListCallback,
		dest="filter",
		default = [],
		help="Filter nodes by group and remarks using keyword."
		)
	parser.add_option(
		"--include-remark",
		action="callback",
		callback = setArgsListCallback,
		dest="remarks",
		default=[],
		help="Filter nodes by remarks using keyword."
		)
	parser.add_option(
		"--include-group",
		action="callback",
		callback = setArgsListCallback,
		dest="group",
		default=[],
		help="Filter nodes by group name using keyword."
		)
	parser.add_option(
		"--exclude",
		action="callback",
		callback = setArgsListCallback,
		dest="efliter",
		default = [],
		help="Exclude nodes by group and remarks using keyword."
		)
	parser.add_option(
		"--exclude-group",
		action="callback",
		callback = setArgsListCallback,
		dest="egfilter",
		default=[],
		help="Exclude nodes by group using keyword."
		)
	parser.add_option(
		"--exclude-remark",
		action="callback",
		callback = setArgsListCallback,
		dest="erfilter",
		default = [],
		help="Exclude nodes by remarks using keyword."
		)
	parser.add_option(
		"-t","--type",
		action="store",
		dest="proxy_type",
		default = "ssr",
		help="Select proxy type in [ssr,ssr-cs,ss,v2ray],default ssr."
		)
	parser.add_option(
		"-y","--yes",
		action="store_true",
		dest="confirmation",
		default=False,
		help="Skip node list confirmation before test."
		)
	parser.add_option(
		"-C","--color",
		action="store",
		dest="result_color",
		default="",
		help="Set the colors when exporting images.."
		)
	parser.add_option(
		"-s","--split",
		action="store",
		dest="split_count",
		default="-1",
		help="Set the number of nodes displayed in a single image when exporting images."
		)
	parser.add_option(
		"-S","--sort",
		action="store",
		dest="sort_method",
		default="",
		help="Select sort method in [speed,rspeed,ping,rping],default not sorted."
		)
	parser.add_option(
		"-i","--import",
		action="store",
		dest="import_file",
		default="",
		help="Import test result from json file and export it."
		)
	parser.add_option(
		"--debug",
		action="store_true",
		dest="debug",
		default=False,
		help="Run program in debug mode."
		)
	parser.add_option(
		"--paolu",
		action="store_true",
		dest="paolu",
		default=False,
		help="如题"
		)

def export(Result,split = 0,exportType= 0,color="origin"):
	er = ExportResult()
	er.setColors(color)
	if (not exportType):
		er.exportAsJson(Result)
		return
	if (split > 0):
		i = 0
		id = 1
		while (i < len(Result)):
			_list = []
			for j in range(0,split):
				_list.append(Result[i])
				i += 1
				if (i >= len(Result)):
					break
			er.exportAsPng(_list,id)
			id += 1
	else:
		er.exportAsPng(Result)

def sortBySpeed(result):
	return result["dspeed"]

def sortByPing(result):
	return result["ping"]

def sortResult(result,sortMethod):
	if (sortMethod != ""):
		if (sortMethod == "SPEED"):
			result.sort(key=sortBySpeed,reverse=True)
		elif(sortMethod == "REVERSE_SPEED"):
			result.sort(key=sortBySpeed)
		elif(sortMethod == "PING"):
			result.sort(key=sortByPing)
		elif(sortMethod == "REVERSE_PING"):
			result.sort(key=sortByPing,reverse=True)
	return result

if (__name__ == "__main__"):

	DEBUG = False
	CONFIG_LOAD_MODE = 0 #0 for import result,1 for guiconfig,2 for subscription url
	CONFIG_FILENAME = ""
	CONFIG_URL = ""
	IMPORT_FILENAME = ""
	FILTER_KEYWORD = []
	FILTER_GROUP_KRYWORD = []
	FILTER_REMARK_KEYWORD = []
	EXCLUDE_KEYWORD = []
	EXCLUDE_GROUP_KEYWORD = []
	EXCLUDE_REMARK_KEWORD = []
	TEST_METHOD = ""
	TEST_MODE = ""
	PROXY_TYPE = "SSR"
	SPLIT_CNT = 0
	SORT_METHOD = ""
	SKIP_COMFIRMATION = False
	RESULT_IMAGE_COLOR = "origin"

	parser = OptionParser(usage="Usage: %prog [options] arg1 arg2...",version="SSR Speed Tool " + VERSION)
	setOpts(parser)
	(options,args) = parser.parse_args()

	if (len(sys.argv) == 1):
		parser.print_help()
		sys.exit(0)

	if (options.paolu):
		for root, dirs, files in os.walk(".", topdown=False):
			for name in files:
				try:
					os.remove(os.path.join(root, name))
				except:
					pass
			for name in dirs:
				try:
					os.remove(os.path.join(root, name))
				except:
					pass
		sys.exit(0)

	print("****** Import Hint 重要提示******")
	print("Before you publicly release your speed test results, be sure to ask the node owner if they agree to the release to avoid unnecessary disputes.")
	print("在您公开发布测速结果之前请务必征得节点拥有者的同意,以避免一些令人烦恼的事情")
	print("*********************************")
	input("Press ENTER to conitnue or Crtl+C to exit.")

	if (options.debug):
		DEBUG = options.debug
		for item in loggerList:
			item.setLevel(logging.DEBUG)
			item.addHandler(fileHandler)
			item.addHandler(consoleHandler)
	else:
		for item in loggerList:
			item.setLevel(logging.INFO)
			item.addHandler(fileHandler)
			item.addHandler(consoleHandler)

	if (logger.level == logging.DEBUG):
		logger.debug("Program running in debug mode")

	if (options.proxy_type):
		if (options.proxy_type.lower() == "ss"):
			PROXY_TYPE = "SS"
			if (checkPlatform() != "Windows" and not checkShadowsocks()):
				sys.exit(1)
		elif (options.proxy_type.lower() == "ssr"):
			PROXY_TYPE = "SSR"
		elif (options.proxy_type.lower() == "ssr-cs"):
			PROXY_TYPE = "SSR-C#"
		elif (options.proxy_type.lower() == "v2ray"):
			PROXY_TYPE = "V2RAY"
		else:
			logger.warn("Unknown proxy type {} ,using default ssr.".format(options.proxy_type))

	#print(options.test_method)
	if (options.test_method == "speedtestnet"):
		TEST_METHOD = "SPEED_TEST_NET"
	elif(options.test_method == "fast"):
		TEST_METHOD = "FAST"
	else:
		TEST_METHOD = "SOCKET"

	if (options.test_mode == "pingonly"):
		TEST_MODE = "TCP_PING"
	elif(options.test_mode == "all"):
		TEST_MODE = "ALL"
	else:
		logger.critical("Invalid test mode : %s" % options.test_mode)
		sys.exit(1)
	

	if (options.confirmation):
		SKIP_COMFIRMATION = options.confirmation
	
	if (options.result_color):
		RESULT_IMAGE_COLOR = options.result_color

	if (options.import_file):
		CONFIG_LOAD_MODE = 0
	elif (options.guiConfig):
		CONFIG_LOAD_MODE = 1
		CONFIG_FILENAME = options.guiConfig
	elif(options.url):
		CONFIG_LOAD_MODE = 2
		CONFIG_URL = options.url
	else:
		logger.error("No config input,exiting...")
		sys.exit(1)


	if (options.filter):
		FILTER_KEYWORD = options.filter
	if (options.group):
		FILTER_GROUP_KRYWORD = options.group
	if (options.remarks):
		FILTER_REMARK_KEYWORD = options.remarks

	if (options.efliter):
		EXCLUDE_KEYWORD = options.efliter
	#	print (EXCLUDE_KEYWORD)
	if (options.egfilter):
		EXCLUDE_GROUP_KEYWORD = options.egfilter
	if (options.erfilter):
		EXCLUDE_REMARK_KEWORD = options.erfilter

	logger.debug(
		"\nFilter keyword : %s\nFilter group : %s\nFilter remark : %s\nExclude keyword : %s\nExclude group : %s\nExclude remark : %s" % (
			str(FILTER_KEYWORD),str(FILTER_GROUP_KRYWORD),str(FILTER_REMARK_KEYWORD),str(EXCLUDE_KEYWORD),str(EXCLUDE_GROUP_KEYWORD),str(EXCLUDE_REMARK_KEWORD)
		)
	)

	if (int(options.split_count) > 0):
		SPLIT_CNT = int(options.split_count)
	
	if (options.sort_method):
		sm = options.sort_method
	#	print(sm)
		if (sm == "speed"):
			SORT_METHOD = "SPEED"
		elif(sm == "rspeed"):
			SORT_METHOD = "REVERSE_SPEED"
		elif(sm == "ping"):
			SORT_METHOD = "PING"
		elif(sm == "rping"):
			SORT_METHOD = "REVERSE_PING"
		else:
			logger.error("Sort method %s not support." % sm)

	if (options.import_file and CONFIG_LOAD_MODE == 0):
		IMPORT_FILENAME = options.import_file
		export(sortResult(importResult.importResult(IMPORT_FILENAME),SORT_METHOD),SPLIT_CNT,2,RESULT_IMAGE_COLOR)
		sys.exit(0)

	if (PROXY_TYPE == "SSR"):
		client = SSRClient()
		uConfigParser = SSRParser()
	elif (PROXY_TYPE == "SSR-C#"):
		client = SSRClient()
		client.useSsrCSharp = True
		uConfigParser = SSRParser()
	elif(PROXY_TYPE == "SS"):
		client = SSClient()
		uConfigParser = SSParser()
	elif(PROXY_TYPE == "V2RAY"):
		client = V2RayClient()
		uConfigParser = V2RayParser()

	if (CONFIG_LOAD_MODE == 1):
		uConfigParser.readGuiConfig(CONFIG_FILENAME)
	else:
		uConfigParser.readSubscriptionConfig(CONFIG_URL)
	uConfigParser.excludeNode([],[],config["excludeRemarks"])
	uConfigParser.filterNode(FILTER_KEYWORD,FILTER_GROUP_KRYWORD,FILTER_REMARK_KEYWORD)
	uConfigParser.excludeNode(EXCLUDE_KEYWORD,EXCLUDE_GROUP_KEYWORD,EXCLUDE_REMARK_KEWORD)
	uConfigParser.printNode()
	logger.info("{} node(s) will be test.".format(len(uConfigParser.getAllConfig())))

	if (TEST_MODE == "TCP_PING"):
		logger.info("Test mode : tcp ping only.")
	else:
		logger.info("Test mode : speed and tcp ping.\nTest method : %s." % TEST_METHOD)

	if (not SKIP_COMFIRMATION):
		ans = input("Before the test please confirm the nodes,Ctrl-C to exit. (Y/N)")
		if (ans == "Y"):
			pass
		else:
			sys.exit(0)

	'''
		{
			"group":"",
			"remarks":"",
			"loss":0,
			"ping":0.01,
			"gping":0.01,
			"dspeed":10214441 #Bytes
		}
	'''
	Result = []
	retryList = []
	retryConfig = []
	retryMode = False
	totalConfCount = 0
	curConfCount = 0

	pfInfo = checkPlatform()

	if (pfInfo == "Unknown"):
		logger.critical("Your system does not supported.Please contact developer.")
		sys.exit(1)

	if (TEST_MODE == "ALL"):
		configs = uConfigParser.getAllConfig()
		totalConfCount = len(configs)
		config = uConfigParser.getNextConfig()
		time.sleep(2)
		while(True):
			if(not config):
				break
			_item = {}
			_item["group"] = config.get("group","N/A")
			_item["remarks"] = config.get("remarks",config["server"])
			config["server_port"] = int(config["server_port"])
			client.startClient(config)
			curConfCount += 1
			logger.info("Starting test for %s - %s [%d/%d]" % (_item["group"],_item["remarks"],curConfCount,totalConfCount))
			time.sleep(1)
			try:
				st = SpeedTest()
				latencyTest = st.tcpPing(config["server"],config["server_port"])
				if (int(latencyTest[0] * 1000) != 0):
					time.sleep(1)
					testRes = st.startTest(TEST_METHOD)
					if (int(testRes[0]) == 0):
						logger.warn("Re-testing node.")
						testRes = st.startTest(TEST_METHOD)
					_item["dspeed"] = testRes[0]
					_item["maxDSpeed"] = testRes[1]
					_item["rawSocketSpeed"] = []
					try:
						_item["rawSocketSpeed"] = testRes[2]
					except:
						pass
					time.sleep(1)
				else:
					_item["dspeed"] = 0
					_item["maxDSpeed"] = 0
					_item["rawSocketSpeed"] = []
				client.stopClient()
				time.sleep(1)
				_item["loss"] = 1 - latencyTest[1]
				_item["ping"] = latencyTest[0]
			#	_item["gping"] = st.googlePing()
				_item["gping"] = 0
				if ((int(_item["dspeed"]) == 0) and (int(latencyTest[0] * 1000) != 0) and (retryMode == False)):
					retryList.append(_item)
					retryConfig.append(config)
				Result.append(_item)
				logger.info(
					"%s - %s - Loss:%s%% - TCP_Ping:%d - AvgSpeed:%.2fMB/s - MaxSpeed:%.2fMB/s" % (
						_item["group"],
						_item["remarks"],
						_item["loss"] * 100,
						int(_item["ping"] * 1000),
						_item["dspeed"] / 1024 / 1024,
						_item["maxDSpeed"] / 1024 / 1024
						)
					)
			except Exception:
				client.stopClient()
				logger.exception("")

			if (True):
				client.stopClient()
				if (retryMode):
					if (retryConfig != []):
						config = retryConfig.pop(0)
					else:
						config = None
				else:
					config = uConfigParser.getNextConfig()

				if (config == None):
					if ((retryMode == True) or (retryList == [])):
						break
					ans = str(input("%d node(s) got 0kb/s,do you want to re-test these node? (Y/N)" % len(retryList))).lower()
					if (ans == "y"):
					#	logger.debug(retryConfig)
						curConfCount = 0
						totalConfCount = len(retryConfig)
						retryMode = True
						config = retryConfig.pop(0)
					#	logger.debug(config)
						continue
					else:
						for r in retryList:
							for s in range(0,len(Result)):
								if (r["remarks"] == Result[s]["remarks"]):
									Result[s]["dspeed"] = r["dspeed"]
									Result[s]["maxDSpeed"] = r["maxDSpeed"]
									Result[s]["ping"] = r["ping"]
									Result[s]["loss"] = r["loss"]
									break
						break
	
	if (TEST_MODE == "TCP_PING"):
		config = uConfigParser.getNextConfig()
		while (True):
			if(not config):
				break
			_item = {}
			_item["group"] = config["group"]
			_item["remarks"] = config["remarks"]
			config["server_port"] = int(config["server_port"])
			st = SpeedTest()
			latencyTest = st.tcpPing(config["server"],config["server_port"])
			_item["loss"] = 1 - latencyTest[1]
			_item["ping"] = latencyTest[0]
			_item["dspeed"] = -1
			_item["maxDSpeed"] = -1
			Result.append(_item)
			logger.info("%s - %s - Loss:%s%% - TCP_Ping:%d" % (_item["group"],_item["remarks"],_item["loss"] * 100,int(_item["ping"] * 1000)))
			config = uConfigParser.getNextConfig()
			if (config == None):break
	export(Result)
	Result = sortResult(Result,SORT_METHOD)
	export(Result,SPLIT_CNT,2,RESULT_IMAGE_COLOR)


