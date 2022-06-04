from warmup_lambda import lambda_risk
import math
import numpy as np
import os
import pandas as pd
import yfinance as yf
from datetime import date, timedelta
from pandas_datareader import data as pdr
import warmup_lambda
import time
import json
import boto3
import pickle
import requests
from concurrent.futures import ThreadPoolExecutor
def ec2_thread(inst):
	flag = 50
	delay = 10
	print("inside thread")
	print("flag!!!!!!!! outside",flag)
	while(flag > 0):
		time.sleep(delay)
		
		try:
			time.sleep(delay)
			url = 'http://'+inst+'/cgi-bin/risk_analysis.py'
			print("trying!!!!!!",url)
			x = requests.get(url,timeout = 5)
			print("flag!!!! inside try",flag,x.status_code)
			if (x.status_code == 200):
				flag = 0
				print("flag value has been changed",flag)
			else:
				flag = flag -1
					  
		except:
			time.sleep(delay)
			flag = flag - 1
			print("inside except and flag = ",flag)    						     																																																		
	return 0

def risk(r,t,h,d,s):
	yf.pdr_override()
	os.environ['AWS_SHARED_CREDENTIALS_FILE']='./cred'
	s3 = boto3.resource('s3',region_name = 'us-east-1')
	bucket = s3.Bucket('mybucketec2')
	today = date.today()
	decadeAgo = today - timedelta(days = 3652)

	data = pdr.get_data_yahoo('TSLA', start=decadeAgo, end=today)

	data['Buy']=0
	data['Sell']=0


	#s_no = 1
	#audit_values['data'] = [s_no,r,t,s,h,d]
	#s_no = s_no +1
	
	#audit_values_json = json.dumps(audit_values)
	#object = s3.Object('mybucketec2','audit.json')
	#result = object.put(Body = audit_values_json)
	
	for i in range(len(data)):
# Hammer
		realbody=math.fabs(data.Open[i]-data.Close[i])
		bodyprojection=0.3*math.fabs(data.Close[i]-data.Open[i])
		if (data.High[i] >= data.Close[i] and data.High[i]-bodyprojection <= data.Close[i] and 
		data.Close[i] > data.Open[i] and data.Open[i] > data.Low[i] and data.Open[i]-data.Low[i] > realbody):
			data.at[data.index[i], 'Buy'] = 1

#print("H", data.Open[i], data.High[i], data.Low[i], data.Close[i])
# Inverted Hammer
		if data.High[i] > data.Close[i] and data.High[i]-data.Close[i] > realbody and data.Close[i] > data.Open[i] and data.Open[i] >= data.Low[i] and data.Open[i] <= data.Low[i]+bodyprojection:
			data.at[data.index[i], 'Buy'] = 1
#print("I", data.Open[i], data.High[i], data.Low[i], data.Close[i])
		# Hanging Man
		if data.High[i] >= data.Open[i] and data.High[i]-bodyprojection <= data.Open[i] and data.Open[i] > data.Close[i] and data.Close[i] > data.Low[i] and data.Close[i]-data.Low[i] >realbody:
			data.at[data.index[i], 'Sell'] = 1
#print("M", data.Open[i], data.High[i], data.Low[i], data.Close[i])
# Shooting Star
		if data.High[i] > data.Open[i] and data.High[i]-data.Open[i] > realbody and data.Open[i] > data.Close[i] and data.Close[i] >= data.Low[i] and data.Close[i] <= data.Low[i]+bodyprojection:
			data.at[data.index[i], 'Sell'] = 1
	#print("S", data.Open[i], data.High[i], data.Low[i], data.Close[i])
	df = pd.DataFrame(columns = ['Date','var95','var99'])
	k = 0
	start = time.time()
	if(s == "Lambda"):
		for i in range(int(h), len(data)):
			if ((t == 'Buy') and (data.Buy[i]) == 1) or ((t == 'Sell') and (data.Sell[i]) == 1): 
				mean=data.Close[i-h:i].pct_change(1).mean()
				std=data.Close[i-h:i].pct_change(1).std()
			#print("Mean :",mean,std)
				var95,var99 = lambda_risk(r,mean,std,d)
				df = df.append({'Date':data.index[i],'var95':var95,'var99':var99},ignore_index = True)
		execution_time = time.time()-start
		

	
	elif(s == "EC2"):
		waiting_for_files = 20
		delay = 5
		
		 
		data_list_mean = []
		data_list_std = []
		data_dict = {}
		for i in range(int(h), len(data)):
			if ((t == 'Buy') and (data.Buy[i]) == 1) or ((t == 'Sell') and (data.Sell[i]) == 1): 
				mean=data.Close[i-h:i].pct_change(1).mean()
				std=data.Close[i-h:i].pct_change(1).std()
				data_list_mean.append(mean)
				data_list_std.append(std)
				df = df.append({'Date':data.index[i]},ignore_index = True)
		data_dict['mean'] = data_list_mean
		data_dict['std'] = data_list_std
		data_dict['shots'] = d
		data_json = json.dumps(data_dict)
		
		# uploading the input data to s3
		print("UPLOADING INPUT FILES TO S3")
		object = s3.Object('mybucketec2','input.json')
		result = object.put(Body = data_json)
		client = boto3.client('ec2',region_name = 'us-east-1')
		#Myec2=client.describe_instances()
		inst = []
		
		while(waiting_for_files > 0):
			try:
				#print("inside try!!!!!!!,length of list",len(warmup_lambda.created_inst))
				
				if(len(warmup_lambda.created_inst) == r):
			
					if(os.environ['warmup'] == 'completed'):
						waiting_for_files = 0
						print("warmup completed")
					
				else:
					waiting_for_files = waiting_for_files - 1
					time.sleep(delay)
			except:
				print("Already warmup completed")
		
		
		start = time.time()
		with ThreadPoolExecutor() as executor:
			results=executor.map(ec2_thread, warmup_lambda.created_inst)
					#args = " 'python3 /tmp/risk_analysis.py "+str(mean)+" "+str(std)+" "+str(d) + "' 'exit'"
		
		execution_time = time.time()-start
		# Taking output files from s3	
		var95 = []
		var99 = []
		for obj in bucket.objects.all():
			key = obj.key
			print("going to take the output files")
			if 'output' in key:
				output_data=json.loads(obj.get()['Body'].read())
				var95.append(output_data['var95'])
				var99.append(output_data['var99'])
			print("deleting all the input and output files from s3")
			if (('input' in key ) or ('output' in key)):
				s3.Object('mybucketec2',key).delete()
			
			
		np_var95 = np.array(var95)
		np_var99 = np.array(var99)
		avg_var95 = np.average(np_var95,axis = 0)
		avg_var99 = np.average(np_var99,axis = 0)
		#df = df.append({'var95':avg_var95,'var99':avg_var99},ignore_index = True)
		df['var95'] = avg_var95.tolist() 
		df['var99'] = avg_var99.tolist()
					
		#print("Values to be added",avg_var95)
		
	
	print(df.head(5))

	return (df,execution_time)	
			
