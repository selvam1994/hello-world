#-------------------------------------------------------------------------------
# Copyright 2017 Cognizant Technology Solutions
# 
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License.  You may obtain a copy
# of the License at
# 
#   http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
# License for the specific language governing permissions and limitations under
# the License.
#-------------------------------------------------------------------------------
'''
Created on May 31, 2017

@author: 446620
'''
import json
import datetime
import time
from time import mktime
from dateutil import parser
from ....core.BaseAgent import BaseAgent
class UrbanCodeDeployAgent(BaseAgent):
	def process(self):
		userid = self.config.get("userid", '')
		passwd = self.config.get("passwd", '')
		baseUrl = self.config.get("baseUrl", '')
		reportType = self.config.get("reportType", '')
		startFrom = self.config.get("startFrom", '')
		componentExecution = self.config.get("componentExecution", '')
		timeNow = datetime.datetime.now()
		timeNow = long((mktime(timeNow.timetuple()) + timeNow.microsecond/1000000.0) * 1000)
		if not componentExecution:
			if not self.tracking.get("lastUpdated",None):
				startFrom = parser.parse(self.config.get("startFrom", ''))
				startFrom = long((mktime(startFrom.timetuple()) + startFrom.microsecond/1000000.0) * 1000)
			else:
				startFrom = self.tracking.get("lastUpdated", None)
			ucdUrl = baseUrl+"/rest/report/adHoc?dateRange=custom&date_low="+str(startFrom)+"&date_hi="+str(timeNow)+"&orderField=date&sortType=desc&type="+str(reportType)
			#print(ucdUrl)
			response = self.getResponse(ucdUrl, 'GET', userid, passwd, None)
			data = []
			responseTemplate = self.getResponseTemplate()
			for item in range(len(response["items"][0])):
				data += self.parseResponse(responseTemplate, response["items"][0][item])
			self.tracking["lastUpdated"] = timeNow
			self.publishToolsData(data)
			self.updateTrackingJson(self.tracking)
		else:
			rowsPerPage = 50
			pageNumber = 1
			exitCondition = True
			startFrom = int(time.mktime(time.strptime(startFrom, '%Y-%m-%d'))) * 1000
			while exitCondition:
				componentUrl = baseUrl+"/rest/deploy/component/details?rowsPerPage="+str(rowsPerPage)+"&pageNumber="+str(pageNumber)+"&orderField=name&sortType=asc&filterFields=active&filterValue_active=true&filterType_active=eq&filterClass_active=Boolean&outputType=BASIC&otType=SECURITY&outputType=LINKED"
				#print("componentUrl - ", componentUrl)
				componentResponse = self.getResponse(componentUrl, 'GET', userid, passwd, None)
				#print(len(componentResponse))
				# for each component ID calling processDeploymentData to execute deployment URL to get the deployments detail.
				for i in range(len(componentResponse)):
					print("component name--------",componentResponse[i]["name"],componentResponse[i]["id"])
					self.processDeploymentData(baseUrl, componentResponse[i]["id"], userid, passwd, startFrom, timeNow)
				pageNumber += 1
				exitCondition = len(componentResponse) > 0
				#print("main cnodition----------------------------------------------------------------------------",exitCondition)
	def processDeploymentData(self, baseUrl, componentId, userid, passwd, startFrom, timeNow):
		rowsPerPage = 100
		pageNumber = 1
		exitCondition = True
		deploymentId = None
		lastDeploymentDate = 0
		lastDeploymentID = ""
		snowChange = ""
		deploymentData = []
		deploymentChildrenData = []
		deploymentResponseTemplate = self.config.get('dynamicTemplate', {}).get('deploymentResponseTemplate',None)
		deploymentResponseTemplateChildren = self.config.get('dynamicTemplate', {}).get('deploymentResponseTemplateChildren',None)
		trackingDetails = self.tracking.get(str(componentId),None)
		#print(trackingDetails)
		if trackingDetails is None:
			trackingDetails = {}
			self.tracking[str(componentId)] = trackingDetails
		else:
			lastDeploymentDate = trackingDetails.get("deployments", {}).get("lastUpdated", None)
			lastDeploymentID = trackingDetails.get("deployments", {}).get("deploymentId", None)
		while exitCondition:
			deploymentUrl = baseUrl+"/rest/deploy/componentProcessRequest/table?rowsPerPage="+str(rowsPerPage)+"&pageNumber="+str(pageNumber)+"&orderField=calendarEntry.scheduledDate&sortType=desc&filterFields=component.id&filterValue_component.id="+str(componentId)+"&filterType_component.id=eq&filterClass_component.id=UUID&outputType=BASIC&outputType=LINKED&outputType=EXTENDED"
			#print("deploymentUrl -", deploymentUrl)
			deploymentResponse = self.getResponse(deploymentUrl, 'GET', userid, passwd, None)
			# Looping through response json to get deployment data
			#print("number------------------------------------------------------------------------------------",(len(deploymentResponse)))
			for i in range(len(deploymentResponse)):
				#print(deploymentResponse[i]["startTime"] ,"----",lastDeploymentDate,"-----",startFrom)
				#print(deploymentResponse[i]["startTime"] > lastDeploymentDate)
				#print("in")
				#print(deploymentResponse[i]["startTime"])
				#print(lastDeploymentDate)
				#print(startFrom)
				#print(deploymentResponse[i]["startTime"] > lastDeploymentDate) and (deploymentResponse[i]["startTime"] > startFrom)
				if (deploymentResponse[i].get("startTime",-1) > lastDeploymentDate) and (deploymentResponse[i].get("startTime",-1) > startFrom):
					#print("inside while for if")
					injectDataChild = {"componentId": componentId, "applicationId": deploymentResponse[i]["application"]["id"], "dataType": "step"}
					for x in range(len(deploymentResponse[i]["rootTrace"]["children"])):
						deploymentChildrenData += (self.parseResponse(deploymentResponseTemplateChildren, deploymentResponse[i]["rootTrace"]["children"][x], injectDataChild))
					#Looping through contextProperties to get snow change value
					for y in range(len(deploymentResponse[i]["contextProperties"])):
						if(deploymentResponse[i]["contextProperties"][y]["name"] == "snow.change"):
							snowChange = deploymentResponse[i]["contextProperties"][y]["value"]
					injectDataParrent = {"dataType": "deployment", "snowChange": snowChange}
					deploymentData += (self.parseResponse(deploymentResponseTemplate, deploymentResponse[i], injectDataParrent))
					if deploymentId == None:
						deploymentId = deploymentResponse[0]["id"]
						timeNow = deploymentResponse[0]["startTime"]
					#self.publishToolsData(deploymentData)
					ucdDepMetadata = {"dataUpdateSupported" : True,"uniqueKey" : ["id","componentId"]}
					self.publishToolsData(deploymentData,ucdDepMetadata)
					#self.publishToolsData(deploymentChildrenData)
					ucdDepChildMetadata = {"dataUpdateSupported" : True,"uniqueKey" : ["deploymentId","componentId"]}
					self.publishToolsData(deploymentChildrenData,ucdDepChildMetadata)
					deploymentData = []
					deploymentChildrenData = []
				else:
					pass
				#print("out")
				#print(i)
			pageNumber += 1
			exitCondition = len(deploymentResponse) > 0
			#print("exitCondition----------------------------------------------------------------------------",exitCondition)
		# Update tracking json with the last captured deployment time
		trackingDetails["deployments"] = {"deploymentId": deploymentId, "lastUpdated": timeNow}
		print("trCKING DETAILS----",trackingDetails)
		self.tracking[str(componentId)] = trackingDetails
		#print(self.tracking[str(componentId)])
		self.updateTrackingJson(self.tracking)
if __name__ == "__main__":
	UrbanCodeDeployAgent()
