#!/usr/bin/python3
import os
import time
import math
import random
import os
import json
import pickle
import boto3
import cgitb

cgitb.enable()
print("Content-Type: text/html;charset=utf-8")
print("")
start = time.time()
s3 = boto3.resource('s3',region_name = 'us-east-1')
bucket = s3.Bucket('mybucketec2')
for obj in bucket.objects.all():
	key = obj.key
	if key == 'input.json':
		data_dict = json.loads(obj.get()['Body'].read())
		
	#mydict = json.loads(body)
	#print(mydict)
		#print(data_dict['mean'])
mean = data_dict['mean']
std = data_dict['std']
shots= data_dict['shots']
shots_lst = [shots for i in range(len(mean))]
#print(type(shots))
#print(std)
def fun1(mean,std,shots):
#	print(mean,std,shots)
		# generate rather larger (simulated) series with same broad characteristics
	simulated = [random.gauss(mean,std) for x in range(shots)]
		# sort, and pick 95% and 99% losses (not distinguishing any trading position)
	simulated.sort(reverse=True)
	var95 = simulated[int(len(simulated)*0.95)]
	var99 = simulated[int(len(simulated)*0.99)]
	#print(var95, var99)
	return var95,var99

v95 = list(map(fun1,mean,std,shots_lst))

out = []

var95 = [each[0] for each in v95]
var99 = [each[1] for each in v95]

print("Output:::::::::::::::::::::::::::::::::::::::::")
#print(v95)
#print(var95)
out.append(var95)
out.append(var99)
#print('out :',out)

random_num =random.randint(1,1000)
file_name = 'output'+str(random_num)+'.json'


data_dict = {}

data_dict['var95'] =  out[0]
data_dict['var99'] = out[1]
data_json = json.dumps(data_dict)


object = s3.Object('mybucketec2',file_name)
result = object.put(Body = data_json)

execution_time = time.time()-start


