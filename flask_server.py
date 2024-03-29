from flask import Flask
from flask import request, jsonify
from kubernetes import client, config
from json import JSONEncoder
import os, uuid, base64, json, sys, argparse
from git.repo.base import Repo
from pathlib import Path
import yaml


application = Flask(__name__)

### Define vars

projectList = []
connectionsList = []

### Define functions

# Pulls the triggering webhooks AzureDev's repo address and clones it to the local docker container
def pullTargetRepo(repoTarget):

    cloned_repo = Repo.clone_from(repoTarget, "./src")

    return cloned_repo


# Checks the purposed Name for the project to make sure it's not already created
def checkProjectNameSecret( purposedName , projectFullName ):

    client.configuration.assert_hostname = False

    api_instance = client.CoreV1Api()

    clusterProjectList = api_instance.list_namespaced_secret(
        namespace="default", pretty=True
    )

    for item in clusterProjectList.items:

        tempDetails = yaml.load(str(item))

        if type(tempDetails["metadata"]['annotations']) == dict and 'projectName' in tempDetails["metadata"]['annotations'].keys() and tempDetails["metadata"]['annotations']['projectName'] == projectFullName:
            
            print('Failed: Project Full Name already deployed in target cluster')
            
            return False
    
        elif tempDetails["metadata"]['name'] == purposedName:

            print ( 'Failed: Project Purposed Secret already deployed in target cluster' )

            return False

    return True

# Gets a List of project/jobnames from the repo
def getJobs():

    projectNameList = [x.name for x in Path("./src/_brigade").iterdir() if x.is_dir()]

    for item in projectNameList:

        projectName = item

        jobList = [
            x.name for x in Path("./src/_brigade/" + projectName).iterdir() if x.is_dir()
        ]

    global jobs

    jobs = {}

    for job in jobList:

        with open(
            "./src/_brigade/" + projectName + "/" + job + "/gb.json"
        ) as json_file:

            jobDetails = json.load(json_file)

        with open(
            "./src/_brigade/" + projectName + "/" + job + "/brigade.js"
        ) as brigadeStore:

            brigadeScript = brigadeStore.read()

        jobs[job] = jobDetails

        jobs[job]["brigade-script"] = brigadeScript

    return jobs

# Creates new project/job
def createNewJob(jobs):
    
    for k, v in jobs.items():

            prodID = str(uuid.uuid4())

            projectFullName = str(v["projectName"])+ "/" + str(v["jobName"])

            purposedName = "greenberet-" + str(prodID)

            connectionHold = {}

            client.configuration.assert_hostname = False

            api_instance = client.CoreV1Api()

            sec = client.V1Secret()

            if checkProjectNameSecret(purposedName, projectFullName) == False:

               print("Bad Project Secret or Project Full Name - Already exist")

               break
               
            v["Project-Secret-Name"] = purposedName

            sec.metadata = client.V1ObjectMeta(
               name=v["Project-Secret-Name"],
               namespace="default",
               labels={"app": "brigade", "component": "project", "heritage": "brigade"},
               annotations={"projectName": str(projectFullName)},
            )

            sec.type = "brigade.sh/project"

            sec.string_data = {
               "defaultScript": v["brigade-script"],
               "genericGatewaySecret": v["gatewaySecret"],
            }

            api_instance.create_namespaced_secret(namespace="default", body=sec)

            connectionHold["Project Name"] = v["Project-Secret-Name"]

            connectionHold["Job Name"] = str(k)

            connectionHold["Job Secret"] = v["gatewaySecret"]

            connectionsList.append(connectionHold)

    return connectionsList

# Replaces an old job with new brigade.js
def createReplaceJob(jobs):
    return



# Various Checks before passing the jobs off to the correct handler function
def createProjects(jobs):
# Check the project has a gbJobHandler Set
    for item in jobs:

        try:

            jobs[item]['gbJobHandler'] in jobs and None != jobs[item]['gbJobHandler']
        
        except:

            print('Triggered because of missing data in gb.json')
            
            raise

    for eachJob in jobs:

        if jobs[eachJob]['gbJobHandler'] == 'new':
    
            print('Trigger Project New function/class with new flag')
    
            createNewJob(jobs)   
    
        elif jobs[eachJob]['gbJobHandler'] == 'replace':
    
            print('Trigger Project createProject with replace flag')

            createReplaceJob(jobs)

        elif jobs[eachJob]['gbJobHandler'] != 'new' and jobs[eachJob]['gbJobHandler'] != 'replace':
    
            print('Complain and exit, must have gbJobHandler to avoid harmful rollouts' )

            return print('No GB handler!!!!')
    return


# routing clean up from incoming web request
application.url_map.strict_slashes = False

# catches any routing artifacts and forces the request to the correct location and the correct method
@application.route("/<path:dummy>", methods=["POST"])

#Main Flask Function that runs when a request is processed 
def fallback(dummy):

    # demo request stored locally for testing comment out to remove
    with open("demo_request.json") as json_file:

        incomingRequest = json.load(json_file)

    # Create dictonary to hold our answer
    response = {}

    #  Get the Job Info
    getJobs()

    # Main Project handler, will setup new or replacement job
    createProjects(jobs)

    # Set our response object to be returned to the incoming call
    response["Response Message"] = connectionsList

    # Return our response in json format
    return jsonify(response.get("Response Message"))

# Starts the flask app
if __name__ == "__main__":

    try:

        config.load_incluster_config()

    except:

        config.load_kube_config()

    application.run(host="0.0.0.0")

