#######################################################################################
#  
#  Green Barrett Server for AKS Brigade & StrategyWise Azure DevOps 
#  Company: StrategyWise
#  Author: cphillips
#  Date: 6/05/19
#
#  
# ##################################################################################### 

from flask import Flask
from flask import request, jsonify
from kubernetes import client, config
from json import JSONEncoder
import os, uuid, base64, json, sys, argparse
from git.repo.base import Repo
from pathlib import Path


application = Flask(__name__)
#Define some vars

projectList = []
connectionsList = []


#Define some functions

def pullTargetRepo (repoTarget):
     cloned_repo = Repo.clone_from(repoTarget, './src')
     return cloned_repo

def getJobs ():
     projectNameList = [x.name for x in Path("./src/_brigade").iterdir() if x.is_dir()]
     for item in projectNameList:
          projectName = item
     jobList = [x.name for x in Path('./src/_brigade/' + projectName).iterdir() if x.is_dir()]
     global jobs
     jobs = {}
     for job in jobList:
          with open("./src/_brigade/" + projectName + "/" + job + "/gb.json") as json_file:  
               jobAdd = json.load(json_file)
          with open("./src/_brigade/" + projectName + "/" + job + "/brigade.js") as brigadeStore:  
               brigadeScript = brigadeStore.read()
          jobs[job] = jobAdd
          jobs[job]['brigade-script'] = brigadeScript
     return jobs

def createProjects(jobs):
     for k,v in jobs.items():
          connectionHold = {}
          client.configuration.assert_hostname = False
          api_instance = client.CoreV1Api()
          sec = client.V1Secret()
          prodID = str(uuid.uuid4())
          v['Project-Name'] = "greenberet-" + str(prodID)
          sec.metadata = client.V1ObjectMeta(
               name=v["Project-Name"],
               namespace="default",
               labels={"app": "brigade", "component": "project", "heritage": "brigade"}
          )
          sec.type = "brigade.sh/project"
          sec.string_data = {
               "defaultScript": v['brigade-script'],
               "genericGatewaySecret": v['gatewaySecret']
          }
          api_instance.create_namespaced_secret(namespace="default", body=sec)
          connectionHold['Project Name'] = v["Project-Name"]
          connectionHold['Job Name'] = str(k)
          connectionHold['Job Secret'] = v['gatewaySecret']
          connectionsList.append(connectionHold)
     return connectionsList


# def checkProjectName ():
     


#routing clean up

application.url_map.strict_slashes = False

#catches any routing artifacts and forces the request to the correct location and the correct method
@application.route('/<path:dummy>', methods=['POST'])

#Serves up the routing, and loads the response, also grabs the incoming varibles from the json via 'feature_array'. 
# ! - 'feature_array' much be set to match what your incoming pickled model is expecting to see

def fallback(dummy):
    
    #Get our incoming varibles from the incoming json array/modify to fit your input target

    #incomingRequest = request.get_json.body
    
    #demo request stored locally for testing comment out to remove
    with open('demo_request.json') as json_file:
         incomingRequest = json.load(json_file)
    #Create dictonary to hold our answer
    response = {}
    #Set our Repo to Clone
#     repoTarget = response['Response Message']['resource']['repository']['remoteUrl']
    #Pull our target repo
#     pullTargetRepo(repoTarget)
    #Get the Job Info
    getJobs()
    #Set the jobs into brigade and return the gateway info for each.  
    createProjects(jobs)
    #Set our predict var
    response['Response Message'] = connectionsList
    #Return our response in json format
    return jsonify(response.get('Response Message'))


#Starts the flask app

if __name__ == '__main__':
     try:
          config.load_incluster_config()
     except:
          config.load_kube_config()
     
     application.run(host='0.0.0.0')