#Developed by Artem.Ageev (c)
#CreatedDate: 20.04.2017
#UpdatedDate: 05.09.2017
#v7

import os
import sys
import getopt
import json
import requests
import csv
import time

#currently https proxy (BURP suite) is used to debug HTTP traffic. 
#Options proxies=proxies and verify=False added to all HTTPS requests.
#2 strings below are used to supress https failed certificate check warning. Remove for prod
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

API_TOKEN = "<YOUR TOKEN HERE>"
ITRP_URL = "https://api.itrp.qa/v1/" #QA
#ITRP_URL = "https://api.itrp.com/v1/" #Production
HEADERS = {"X-ITRP-Account" : "canonit", "Content-Type": "application/json"}
PROXIES = {"https": "localhost:8080"}
USE_PROXY = False  #dont change this. Use /p key if you need proxy
DEFAULT_CI_ID = [598103] #Security Operations special CI (Unknown CI)
DEFAULT_TEAM_ID = '5807'  #SecOps
DEFAULT_SI_ID = '29022' #Workstation, CENV
DEFAULT_USER_ID = '1250158' #Artem Ageev
CONNECTION_DELAY = 0.5 #In Seconds

# Typical request consists of this variables:
#
# ci_labels=["CEU-LT143503", "CEU-LT139444", "CBL-LT000094"]
# ci_ids = [540396, 442754]
# service_instance_id = "35456"
# team_id = "5807"
# status = "assigned"
# subject = "test3"
# note = "testtest3"
# category = "incident" # or "rfi"
# impact = "low"
# (optional)
# requested_by_id = 1250158
# requested_for_id = 1250158


def main(argv):
#step 0. Prepare variables

	filename = ""
	default_assign_unknown_to_secops = False
	request_ci_id = True
	request_si_id = True
	request_team_id = True
	request_for_CI_owner = False
	CI_info = []
	SI_id = ''

#step 1. Read file to dictionary
	try:
		opts, args = getopt.getopt(argv, "hi:pcstxu", ["filename="])
	except getopt.GetoptError:
		print("Input error. Correct syntax: csv2itrp.py -i <CSV file> [-p, -c, -s, -t, -x, -u]")
		sys.exit(2)
	for opt, arg in opts:
		if opt == "-h":
			print("csv2itrp.py")
			print("-i <CSV file> 	input CSV file")
			print("-p 	use proxy")
			print("-c 	do not resolve CI_ID from CI_label via ITRP website")
			print("-s 	do not resolve service instance ID from CI_ID via ITRP website")
			print("-t 	do not resolve Team_ID from CI_label via ITRP website")
			print("-x 	assign ticket to defaul team if no proper team could be found")
			print("-u 	use CI user as a requester user ID")
			sys.exit()
		elif opt in ("-i", "--ifile"):
			filename = arg
		elif opt == "-p":
			global USE_PROXY
			USE_PROXY = True
		elif opt == "-c":
			request_ci_id = False
		elif opt == "-s":
			request_si_id = False
		elif opt == "-t":
			request_team_id = False
		elif opt == "-x":
			default_assign_unknown_to_secops = True
		elif opt == "-u":
			request_for_CI_owner = True

	#safety check
	if not safety_check():
		return

	#read CSV file content to data[]
	csvfile = open(filename, 'r')
	data = list(csv.DictReader(csvfile, delimiter=';', dialect='excel'))  # list() will read everything in memory
	csvfile.close()

#step 2
#get CI info
	if request_ci_id or request_si_id or request_team_id: #only send request if additional info needed
		for request in data:
			CI_info = get_CI_info(request['ci_labels']) #will return error_msg, ci_ids, team_id
			request['note'] += ''.join(CI_info[0])  #attach error message to request note
		
			if request_ci_id:									#if you want to resolve CI_ID
				if CI_info[1]:									#if resolved CI_ID not blank
					request['ci_ids'] = CI_info[1]
				else:
					if 'ci_ids' in request:							#if ci_ids key exists
						if not request['ci_ids']:					#if ci_ids key empty (no CI_IDS key in file)
							request['ci_ids'] = DEFAULT_CI_ID		#use default
					else:											#if ci_ids not exists - add it with default value
						request['ci_ids'] = DEFAULT_CI_ID

			if request_team_id:
				if CI_info[2]:
					request['team_id'] = CI_info[2]
				else:
					if 'team_id' in request:
						if not request['team_id']:
							request['team_id'] = DEFAULT_TEAM_ID
					else:
						request['team_id'] = DEFAULT_TEAM_ID

			if request_si_id:
				if 'ci_ids' in request:	
					SI_id = get_SI(request['ci_ids'][0]) 
					if SI_id:
						request['service_instance_id'] = SI_id
					else:
						if 'service_instance_id' in request:
							if not request['service_instance_id']:
								request['service_instance_id'] = DEFAULT_SI_ID

			if request_for_CI_owner:
				if 'ci_ids' in request:
					user_id = get_CI_user(request['ci_ids'][0])
					if user_id:
						request['requested_by_id'] = user_id
						request['requested_for_id'] = user_id
					else:
						request['requested_by_id'] = DEFAULT_USER_ID
						request['requested_for_id'] = DEFAULT_USER_ID

#step 3
#create requests
	for request in data:	
		if request['team_id'] == DEFAULT_TEAM_ID:
			if default_assign_unknown_to_secops:
				print("[Warning] No team assosiated with CI ID: "+ str(request["ci_ids"])+ ". Assigning to SecOps.")
				create_request(request)
			else:
				print("[Warning] No team ID assosiated with CI ID: "+ str(request["ci_ids"]) + ". Skipping this request.")
		else:
			create_request(request)

#will sent GET request to https://api.itrp.com/v1/cis?label= and grab ci_ids + team_id
def get_CI_info(ci_labels):
	ci_array = ci_labels.split(",")
	ci_ids=[]
	error_msg=[]
	team_id = ''

	for ci in ci_array:
		time.sleep(CONNECTION_DELAY)
		if USE_PROXY:
			r = requests.get(ITRP_URL+"cis"+"?api_token="+API_TOKEN+"&label="+ci, headers = HEADERS, 
				proxies=PROXIES, verify=False)
		else:
			r = requests.get(ITRP_URL+"cis"+"?api_token="+API_TOKEN+"&label="+ci, headers = HEADERS)

		try:
			ci_ids.append(r.json()[0][u'id'])
		except:
			print("[Warning] " + ci + " not exists in ITRP")
			error_msg.append(" [Warning] Affected CI <" + ci + "> not exists in ITRP. Please add it.")

		try:
			team_id = r.json()[0][u'support_team'][u'id']
		except:
			print("[Warning] CI: " + ci + " not assigned to a team")

		return [''.join(error_msg), ci_ids, team_id]

def get_SI(ci_id):
	si_id = ''

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
		print('[Warning] Could not get SI_ID for CI_ID:'+ str(ci_id))

	return si_id

def get_CI_user(ci_id):
	#will return ID of the owner of CI (e.g. 1250158 for Artem Ageev)
	#test URL: https://api.itrp.qa/v1/cis/540396/users?api_token=<TOKEN>

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
#	for i in ('team_id', 'service_instance_id', 'status', 'subject', 'note', 'category', 'impact', 'ci_ids'):
#		payload[i] = locals()[i]
	time.sleep(CONNECTION_DELAY)
	if USE_PROXY:
		r = requests.post(ITRP_URL+"requests", data=json.dumps(request), headers = HEADERS, proxies=PROXIES, verify=False)
	else:
		r = requests.post(ITRP_URL+"requests", data=json.dumps(request), headers = HEADERS)

	try:
		print("[INFO] Request N " + str(r.json()[u'id']) + " successfully created")
	except:
		if u"errors" in r.json():
			if "ci_labels" in request:
				print("[Error] Request not created. CI: " + request["ci_labels"] + ". Error MSG:" + str(r.json()[u'errors']))
			else:
				print("[Error] Request not created" + ". Error MSG:" + str(r.json()[u'errors']))
	return

def safety_check():
	print("Current ITRP URL is " + ITRP_URL + ". Ready to proceed? (y/n)")

	keypressed = input()

	if keypressed == "Y" or keypressed == "y":
		return True
	else:
		print("Canceled by user. Exiting..")
		return False


print("============================= CSV to ITRP script =============================")
print("(c) Artyom Ageyev artem.ageev@canon-europe.com ")

main(sys.argv[1:])