#Developed by Artem.Ageev (c)
#CreatedDate: 20.04.2017
#UpdatedDate: 13.11.2017
#v9.1

import os
import sys
import getopt
import json
import requests
import csv
import time
import configparser #this module should be installed separately. "pip install configparser"

# currently https proxy (BURP suite) is used to debug HTTP traffic. 
# Options proxies=proxies and verify=False added to all HTTPS requests.
# 2 strings below are used to supress https failed certificate check warning. This is only for Debugging
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

template_request = dict.fromkeys(['ci_labels', 'ci_ids', 'service_instance_id', 'team_id', 'status', 'subject', 'note', 'category', \
				'impact', 'requested_by_id', 'requested_for_id', 'primary_email', 'name'])

## get your token here https://.itrp.qa/account/personal_information

## To pretty print requests
# print(json.dumps(r.json(), indent=4, sort_keys=True)) #where r is server output

## Curl example
# curl --header "X-ITRP-Account: " https://api.itrp.com/v1/people?api_token=&name="Artem Ageev"

def main(argv):
	#choose between prod and QA environment, get configuration, read parameters
	set_environment(argv)

	# read CSV file content to data[]
	csvfile = open(filename, 'r')
	data = list(csv.DictReader(csvfile, delimiter=';', dialect='excel'))  # list() will read everything in memory
	csvfile.close()

	for r in data:
		request = template_request.copy()
		request.update(r) # make sure that you will not get error "key not exist" anymore

		if not DONT_RESOLVE_ANYTHING:
			enrich_request(request) # add all required fields to the template
		create_request(request)

	print("[INFO] All done! check csv2itrp.log for request numbers")

def enrich_request(request):
	ci_info = [None]
	si_id = ''
	user_id = ''

	if request_from_username:
		ci_info = get_info_from_email(request['primary_email'])  #[error_msg, ci_ids, team_id, user_id]

		request['note'] += ''.join(ci_info[0]) 
		if not request['ci_ids']:
			request['ci_ids'] = ci_info[1]
		if not request['team_id']:
			request['team_id'] = ci_info[2]
		if not request['requested_by_id'] and not request['requested_for_id']:
			request['requested_for_id'] = ci_info[3]
			request['requested_by_id'] = ci_info[3]	

	if not request['ci_ids'] and request['ci_labels']:
		ci_info = get_CI_info(request['ci_labels']) #will return error_msg, ci_ids, team_id
		request['note'] += ''.join(ci_info[0]) 
		if not request['ci_ids']:
			request['ci_ids'] = ci_info[1]
		if not request['team_id']:
			request['team_id'] = ci_info[2]

	if request_for_CI_owner and request['ci_ids']:
		user_id = get_CI_user(request['ci_ids'])
		if user_id:
			if not request['requested_by_id']:
				request['requested_by_id'] = user_id
			if not request['requested_for_id']:
				request['requested_for_id'] = user_id
			
	if not request['service_instance_id'] and request['ci_ids']:
		si_id = get_SI(request['ci_ids'][0]) 
		if si_id:
			request['service_instance_id'] = si_id

	# if empty set defaul value
	if not request['service_instance_id']:
		request['service_instance_id'] = DEFAULT_SI_ID
	if not request['team_id']:
		request['team_id'] = DEFAULT_TEAM_ID
	if not request['requested_by_id'] and not request['requested_for_id']:
		request['requested_for_id'] = DEFAULT_USER_ID
		request['requested_by_id'] = DEFAULT_USER_ID


#will sent GET request to https://api.itrp.com/v1/cis?label= and grab ci_ids + team_id
def get_CI_info(ci_labels):
	ci_ids=[]
	error_msg=[]
	team_id = ''

	time.sleep(CONNECTION_DELAY)

	if USE_PROXY:
		r = requests.get(ITRP_URL+"cis"+"?api_token="+API_TOKEN+"&label="+str(ci_labels), headers = HEADERS, 
			proxies=PROXIES, verify=False)
	else:
		r = requests.get(ITRP_URL+"cis"+"?api_token="+API_TOKEN+"&label="+str(ci_labels), headers = HEADERS)
	try:
		ci_ids.append(r.json()[0][u'id'])
	except:
		print("[Warning] " + str(ci_labels) + " not exists in ITRP")
		error_msg.append(" [Warning] Affected CI <" + str(ci_labels) + "> not exists in ITRP. Please add it.")


	try:
		team_id = r.json()[0][u'support_team'][u'id']
	except:
		print("[Warning] CI: " + str(ci_labels) + " not assigned to a team")
	return [''.join(error_msg), ci_ids, team_id]

def get_SI(ci_ids):
	si_id = ''
	if type(ci_ids) == list:
		ci_id = ci_ids[0]
	else:
		ci_id = ci_ids

	time.sleep(CONNECTION_DELAY)
	if USE_PROXY: 
		r = requests.get(ITRP_URL+"requests/ci_si"+"?api_token="+API_TOKEN+"&ci_ids="+str(ci_id), 
			headers = HEADERS, proxies=PROXIES, verify=False)
	else:
		r = requests.get(ITRP_URL+"requests/ci_si"+"?api_token="+API_TOKEN+"&ci_ids="+str(ci_id), 
			headers = HEADERS)
	
	try:
		si_id = r.json()[u'id']
	except:
		print('[ERROR] Could not get SI_ID for CI_ID:'+ str(ci_id))

	return si_id

def get_CI_user(ci_ids):
	#will return ID of the owner of CI 
	#test URL: https://api.itrp.qa/v1/cis//users?api_token=<TOKEN>
	if type(ci_ids) == list:
		ci_id = ci_ids[0]
	else:
		ci_id = ci_ids

	user_id = ""

	time.sleep(CONNECTION_DELAY)
	if USE_PROXY: 
		r = requests.get(ITRP_URL + "cis/" + str(ci_id) + "/users" + "?api_token=" + API_TOKEN, 
			headers = HEADERS, proxies=PROXIES, verify=False)
	else:
		r = requests.get(ITRP_URL + "cis/" + str(ci_id) + "/users" + "?api_token=" + API_TOKEN, 
			headers = HEADERS)
	
	try:
		user_id = r.json()[0][u'id']
	except:
		print('[Warning] Could not get user_id for CI_ID:'+ str(ci_id))

	return user_id

def create_request(request):
	request['api_token'] = API_TOKEN
	cleaned_request = {k: v for k, v in request.items() if v}  #remove empty keys
	time.sleep(CONNECTION_DELAY)
	if USE_PROXY:
		r = requests.post(ITRP_URL+"requests", data=json.dumps(cleaned_request), headers = HEADERS, proxies=PROXIES, verify=False)
	else:
		r = requests.post(ITRP_URL+"requests", data=json.dumps(cleaned_request), headers = HEADERS)

	try:
		print("[INFO] request N " + str(r.json()[u'id']) + " successfully created")
		output_requests_N_to_file(str(r.json()[u'id']))
	except:
		if u"errors" in r.json():
			print("[Error] request not created. CI: " + request["ci_labels"] + ". Error MSG:" + str(r.json()[u'errors']))

def output_requests_N_to_file(number):
	with open('csv2itrp.log', 'a') as fp:
		fp.write(number + '\n')

#this will allow user to choose PROD or QA each time
def set_environment(argv):
	global ITRP_URL, HEADERS, PROXIES, CONNECTION_DELAY, API_TOKEN, DEFAULT_TEAM_ID, DEFAULT_SI_ID, DEFAULT_USER_ID
	global filename, request_for_CI_owner, request_from_username, USE_PROXY, VERBOSE, DONT_RESOLVE_ANYTHING
	## <BANNER> ##
	print("============================= CSV to ITRP script =============================")
	## </BANNER> ##

	# Read config
	config = configparser.ConfigParser()
	config.readfp(open('csv2itrp.cfg'))
	API_TOKEN_QA = config.get('ITRP settings', 'API_TOKEN_QA')
	API_TOKEN_PROD = config.get('ITRP settings', 'API_TOKEN_PROD')
	ITRP_URL_QA = config.get('ITRP settings', 'ITRP_URL_QA')
	ITRP_URL_PROD = config.get('ITRP settings', 'ITRP_URL_PROD')
	HEADERS = config._sections['ITRP Headers']
	PROXIES = config._sections['Proxy']
	CONNECTION_DELAY = config.getfloat('Connection settings', 'CONNECTION_DELAY')
	DEFAULT_TEAM_ID = config.get('Defaults', 'DEFAULT_TEAM_ID')
	DEFAULT_SI_ID = config.get('Defaults', 'DEFAULT_SI_ID')
	DEFAULT_USER_ID = config.get('Defaults', 'DEFAULT_USER_ID')

	USE_PROXY = False  #dont change this. Use -p key if you need proxy
	VERBOSE = False #dont change this also. Use -v
	use_QA = False #dont ask, use QA always. -q key
	request_for_CI_owner = True
	request_from_username = False
	DONT_RESOLVE_ANYTHING = False

	try:
		opts, args = getopt.getopt(argv, "hi:punsvq", ["filename="])
	except getopt.GetoptError:
		print("Input error. Correct syntax: csv2itrp.py -i <CSV file> [-p, -u, -n, -s, -v]")
		sys.exit(2)
	for opt, arg in opts:
		if opt == "-h":
			print("csv2itrp.py")
			print("-i, --input <CSV file> 	Input CSV file")
			print("-p, --proxy 	Use proxy")
			print("-u 	Do not use CI user as a requester user ID")
			print("-n 	ci_id, team_id and user_id should be resolved from email or username")
			print("-s 	just create a request. Don't resolve anything")
			print("-v 	verbose output")
			sys.exit()
		elif opt in ("-i", "--input"):
			filename = arg
		elif opt in ("-p", "--proxy"):
			USE_PROXY = True
		elif opt == "-u":
			request_for_CI_owner = False
		elif opt == "-n":
			request_from_username = True
		elif opt == "-v":
			VERBOSE = True
		elif opt == "-s":
			DONT_RESOLVE_ANYTHING = True
		elif opt == "-q":
			use_QA = True

	#Choose between PROD or QA
	print("Please choose ITRP environment:")
	print("    1. Production (url: ", ITRP_URL_PROD, ")")
	print("    2. QA (url: ", ITRP_URL_QA, ")")

	if use_QA:
		API_TOKEN = API_TOKEN_QA
		ITRP_URL = ITRP_URL_QA
		print("[INFO] Working with QA environment because -q was used")
	else:
		keypressed = input()
		if keypressed == "1":
			print("[INFO] Working with Production Environment")
			API_TOKEN = API_TOKEN_PROD
			ITRP_URL = ITRP_URL_PROD
		elif keypressed == "2":
			API_TOKEN = API_TOKEN_QA
			ITRP_URL = ITRP_URL_QA
			print("[INFO] Working with QA environment")
		else:
			print("[ERROR] No environment defined. Exiting..")
			sys.exit()

#this will allow to use email to get CI and TEAM id.
def get_info_from_email(primary_email):
	ci_id = []
	user_id = ''
	
	time.sleep(CONNECTION_DELAY)

	if USE_PROXY:
		r = requests.get(ITRP_URL + "people" + "?api_token=" + API_TOKEN + "&primary_email=" + str(primary_email), 
			headers = HEADERS, proxies=PROXIES, verify=False)
	else:
		r = requests.get(ITRP_URL + "people" + "?api_token=" + API_TOKEN + "&primary_email=" + str(primary_email), 
			headers = HEADERS)

	try:
		user_id = r.json()[0][u'id']
	except:
		print('[Warning] Could not get user_id for email:'+ str(primary_email))
		return ['[ERROR] User "' + str(primary_email) + '" does not exist in ITRP', None, None, None]

	if user_id:
		time.sleep(CONNECTION_DELAY)
		if USE_PROXY:
			r = requests.get(ITRP_URL + "people/" + str(user_id) + "/cis" + "?api_token=" + API_TOKEN,
				headers = HEADERS, proxies=PROXIES, verify=False)
		else:
			r = requests.get(ITRP_URL + "people/" + str(user_id) + "/cis" + "?api_token=" + API_TOKEN, 
				headers = HEADERS)
		try:
			ci_id.append(r.json()[0][u'id'])
			team_id = r.json()[0][u'support_team'][u'id']
		except:
			print('[Warning] Could not get ci_id or team_id for email:'+ primary_email)
			return ['[ERROR] looks like no CI assosiated with this user', None, None, None]

	return ['', ci_id, team_id, user_id]

def writelog(msg):
	if VERBOSE:
		print(str(datetime.datetime.now()) + "\t" + msg)

main(sys.argv[1:])
