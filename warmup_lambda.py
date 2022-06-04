#!/usr/bin/env python3
import time
import http.client
import ast
import os
import boto3
import json

from concurrent.futures import ThreadPoolExecutor
# creates a list of values as long as the number of things we want
# in parallel so we could associate an ID to each. More parallelism here.

def getpage(id,mean,std,shots):
	try:
		host = "4yxufghe91.execute-api.us-east-1.amazonaws.com"
		c = http.client.HTTPSConnection(host)
		json= '{ "key1":'+str(mean)+ ',"key2":'+str(std)+ ',"key3":'+str(shots)+'}'
		c.request("POST", "/default/CW_riskanalysis", json)
		response = c.getresponse()
		data = response.read().decode('utf-8')
		data_dict = ast.literal_eval(data)
		#print(data_dict["var95"])
		
	except IOError:
		print( 'Failed to open ', host ) # Is the Lambda address correct?
	#print(data+" from "+str(id)) # May expose threads as completing in a different order
	return [data_dict["var95"],data_dict["var99"]]
def getpages(runs,mean,std,shots):
	with ThreadPoolExecutor() as executor:
		results=executor.map(getpage, runs,mean,std,shots)
	return results
def warmup_l(r):
	print("This is warmup!!!!!!!!!")
	os.environ['AWS_SHARED_CREDENTIALS_FILE']='./cred'
	start = time.time()
	runs = [value for value in range(r)]
	# giving dummy values for warmup
	mean = [0 for value in range(r)]
	std = [1 for value in range(r)]
	shots = [1 for value in range(r)]
	results = getpages(runs,mean,std,shots)
	warm_up_time = time.time() - start
	print( "Elapsed Time: ", time.time() - start)
	
	s3 = boto3.resource('s3',region_name = 'us-east-1')
	bucket = s3.Bucket('mybucketec2')
	for obj in bucket.objects.all():
		key = obj.key
		if key == 'audit.json':
			data_dict = json.loads(obj.get()['Body'].read())		
	
	data_dict["warm_up_time"].append(warm_up_time)
	audit_values_json = json.dumps(data_dict)
	object = s3.Object('mybucketec2','audit.json')
	result = object.put(Body = audit_values_json)
	print("warmup Completed!!!!!")
	#for result in results: # uncomment to see results in ID order
	 #print(result)

def lambda_risk(r,mean_val,std_val,d_val):
	print("This is the main analysis")
	start = time.time()
	runs = [value for value in range(r)]
	mean = [mean_val for value in range(r)]
	std = [std_val for value in range(r)]
	shots = [d_val for value in range(r)]
	results = getpages(runs,mean,std,shots)
	warm_up_time = time.time() - start
	print( "Elapsed Time: ", time.time() - start)
	average = [0,0]
	for result in results: # uncomment to see results in ID order
	  average = [average[0]+result[0],average[1]+result[1]]
	var95 = average[0]/r
	var99 = average[1]/r 
	return(var95,var99)
	#print("Here it is var95 and var 99",var95,var99)
	 
def create_ec2(r):
	start = time.time()
	os.environ['AWS_SHARED_CREDENTIALS_FILE']='./cred'
	os.environ['warmup'] = 'started'
	# Above line needs to be here before boto3 to ensure cred file is read
	# from the right place
	# Set the user-data we need – use your endpoint
	user_data = """#!/bin/bash
		   wget https://extreme-sinner.ew.r.appspot.com/cacheavoid/setup.bash
		   bash setup.bash"""
	ec2 = boto3.resource('ec2', region_name='us-east-1')
	instances = ec2.create_instances(
		#ImageId = 'ami-0e449176cecc3e577',
		ImageId = 'ami-0ed9277fb7eb570c9', # Amzn Lnx 2 AMI - Kernel 5.10
		MinCount = 1,
		MaxCount = r,
		InstanceType = 't2.micro',
		KeyName = 'kp',  
		SecurityGroups=['Lab4'],
		IamInstanceProfile={
			'Arn':'arn:aws:iam::363460019577:instance-profile/LabInstanceProfile'
			},
		UserData=user_data 
		
	)
	# Wait for AWS to report instance(s) ready.
	global created_inst
	created_inst = []
	for i in instances:
		i.wait_until_running()
	# Reload the instance attributes
		i.load()
		
		
		created_inst.append(i.public_dns_name)
		print("THIS IS THE DNS",i.public_dns_name) # ec2 com address
	time.sleep(5)
	warm_up_time = time.time() - start
	#for audit page	
	s3 = boto3.resource('s3',region_name = 'us-east-1')
	bucket = s3.Bucket('mybucketec2')
	for obj in bucket.objects.all():
		key = obj.key
		if key == 'audit.json':
			data_dict = json.loads(obj.get()['Body'].read())		
	
	data_dict["warm_up_time"].append(warm_up_time)
	audit_values_json = json.dumps(data_dict)
	object = s3.Object('mybucketec2','audit.json')
	result = object.put(Body = audit_values_json)
	os.environ['warmup'] = 'completed'	


	

	
