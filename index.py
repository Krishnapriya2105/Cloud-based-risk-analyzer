import os
import json
import logging
import time
from warmup_lambda import warmup_l,create_ec2
import warmup_lambda
import threading
from flask import Flask, request, render_template,url_for
from risk_analysis import risk
import boto3
os.environ['AWS_SHARED_CREDENTIALS_FILE']='./cred'
app = Flask(__name__)
def data_process(df,r,t,h,d,s,execution_time):
	
	date = df.Date.to_list()
	var95 = df.var95.to_list()
	var95_avg = [sum(var95)/len(var95) for each in var95]
	var99 = df.var99.to_list()
	var99_avg = [sum(var99)/len(var99) for each in var99]
	list_of_list = [['Date','Var95','Var99']]
	for i in range(len(date)):
		list_of_list.append([date[i],var95[i],var99[i]])
	data = 'a:'
	for each in var95:
		data+=str(each) +','
	data = data[:-1]
	data = data + '|'
	for each in var99:
		data+=str(each) +','
	data = data[:-1]
	data = data + '|'
	for each in var95_avg:
		data+=str(each) +','
	data = data[:-1]
	data = data + '|'
	for each in var99_avg:
		data+=str(each) +','
	data = data[:-1]
	date_val ='0:|'
	for i in range(len(date)):
		date[i] = date[i].to_pydatetime()
		date[i] = date[i].strftime('%Y-%m-%d')
	for each in date:
		date_val +=str(each) + '|'	
	date_val = date_val[:-1]
	print("date_val",date_val)
	s3 = boto3.resource('s3',region_name = 'us-east-1')
	bucket = s3.Bucket('mybucketec2')
	for obj in bucket.objects.all():
		key = obj.key
		if key == 'audit.json':
			data_dict = json.loads(obj.get()['Body'].read())		
		
	data_dict["Resource"].append(s)
	data_dict["number of resource"].append(r)
	data_dict["trade_signal"].append(t)
	data_dict["length of History"].append(h)
	data_dict["data_points"].append(d)
	data_dict["var95"].append(var95_avg[0])	
	data_dict["var99"].append(var99_avg[0])
	data_dict["execution_time"].append(execution_time)
	#print("data dict",data_dict,type(data_dict))
	
	
	#print("data dict",data_dict)
		
	audit_values_json = json.dumps(data_dict)
	object = s3.Object('mybucketec2','audit.json')
	result = object.put(Body = audit_values_json)
	return (data,list_of_list,date_val)
	
def doRender(tname, values={}):
	if not os.path.isfile( os.path.join(os.getcwd(), 'templates/'+tname) ): #No file
			return render_template('index.htm')
	return render_template(tname, **values)
	 	
@app.route('/input', methods = ['POST'])
def firstpage():
	if request.method == 'POST':
		global r
		r = int(request.form.get('Resources'))
		global s
		s = request.form.get('select')
		
		if r == '':
			return doRender('index.htm',{'note':'Please specify the number resources'})
		elif s == 'Noselect':
			return doRender('index.htm',{'note':'Please select the Resource type'})
		elif s == 'Lambda':
			warmup_t = threading.Thread(target = warmup_l,args = [int(r)])
			warmup_t.setDaemon(True) # to run in background
			warmup_t.start()
			return doRender('page2.htm',{'s':s,'r':r})
		elif s == 'EC2':
			warmup_t = threading.Thread(target = create_ec2,args = [int(r)])
			warmup_t.setDaemon(True)
			warmup_t.start()
			print("EC2 has to be created")
			return doRender('page2.htm',{'s':s,'r':r})
		else:
			return doRender('page2.htm',{'s':s,'r':r})
			
@app.route('/analysis/<s>/<r>', methods = ['POST'])
def secondpage(s,r):

	if request.method == 'POST':
		t = request.form.get('tradeselect')
		h = int(request.form.get('pricehistory'))
		d = int(request.form.get('datapoints'))
		# for audit page
	
		r = int(r)
		if t == '' or h == '' or d == '':
			return doRender('page2.htm',{'note':'Please specify all the resources'})
		#read the audit page
		
		elif s == 'Lambda':
			df,execution_time = risk(r,t,h,d,s)
			data,list_of_list,date_val = data_process(df,r,t,h,d,s,execution_time)
			
			return doRender('result.htm',{'data':data,'df':list_of_list,'s':s,'r':r,'date':date_val})
		elif s == 'EC2':
			df,execution_time = risk(r,t,h,d,s)
			data,list_of_list,date_val = data_process(df,r,t,h,d,s,execution_time)		
			
			return doRender('result.htm',{'data':data,'df':list_of_list,'s':s,'r':r,'date':date_val})

@app.route('/audit/',methods = ['POST'])
def audit():
	s3 = boto3.resource('s3',region_name = 'us-east-1')
	bucket = s3.Bucket('mybucketec2')
	for obj in bucket.objects.all():
		key = obj.key
		if key == 'audit.json':
			data_dict = json.loads(obj.get()['Body'].read())
	audit_list = [["Resource","number of resource","trade_signal","length of History","data_points","warm_up_time","execution_time","var95","var99"]]
	
	audit_data = list(data_dict.values())
	for i in range(len(audit_data[0])):
		tmp =[]
		for each in audit_data:
			tmp.append(each[i])
		audit_list.append(tmp)			

	return doRender('audit.htm',{'df':audit_list})

@app.route('/terminate',methods = ['POST'])
def terminate():
	os.environ['AWS_SHARED_CREDENTIALS_FILE']='./cred'
	client = boto3.client('ec2',region_name = 'us-east-1')
	Myec2=client.describe_instances()
	inst = []
	for items in Myec2['Reservations']:
		for out in items['Instances']:
	   		inst.append(out['InstanceId'])
	if (len(inst) == 0):
		return doRender('index.htm')
	else:
		print(client.terminate_instances(InstanceIds=(inst)))
			#print("these are the instances")
		return doRender('index.htm')

@app.route('/reset/<s>/<r>',methods = ['POST'])
def reset(s,r):

	return doRender('page2.htm',{'s':s,'r':r})



	
			
@app.route('/cacheavoid/<name>')
def cacheavoid(name):
# file exists?
	if not os.path.isfile( os.path.join(os.getcwd(), 'static/'+name) ):
		return ( 'No such file ' + os.path.join(os.getcwd(), 'static/'+name) )
	f = open ( os.path.join(os.getcwd(), 'static/'+name) )
	contents = f.read()
	f.close()
	return contents	
# catch all other page requests - doRender checks if a page is 
#available (shows it) or not (index)
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def mainPage(path):
	return doRender(path)


		
@app.errorhandler(500)
def server_error(e):
	logging.exception('ERROR!')
	return """
	An error occurred: <pre>{}</pre>
	""".format(e), 500 

if __name__ == '__main__':
	app.run(host='127.0.0.1', port=8080, debug=True)
