from flask import Flask
from flask import request, jsonify
from kubernetes import client, config
from json import JSONEncoder
import os, uuid, base64, json, sys, argparse
from git.repo.base import Repo
from pathlib import Path
import yaml


application = Flask(__name__)
# Define some vars

projectList = []
connectionsList = []

###Define some functions
##

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


# Reads config file from Repo, uses the job names from getJobs() and creates Brigade project/jobs in the cluster
def createProjects(jobs):

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


# routing clean up from incoming web request

application.url_map.strict_slashes = False

# catches any routing artifacts and forces the request to the correct location and the correct method


@application.route("/<path:dummy>", methods=["POST"])

# Main Flask Command function - trigger on successful call into Flask via Gunicorn


def fallback(dummy):

    ## ** Dev - Testing: incomingRequest = request.get_json.body

    # demo request stored locally for testing comment out to remove
    with open("demo_request.json") as json_file:

        incomingRequest = json.load(json_file)

    # Create dictonary to hold our answer

    response = {}

    ## ** Dev - Testing: Set our Repo to Clone
    ## ** Dev - Testing:    repoTarget = response['Response Message']['resource']['repository']['remoteUrl']
    ## ** Dev - Testing: Pull our target repo
    ## ** Dev - Testing:   pullTargetRepo(repoTarget)

    #  Get the Job Info
    getJobs()

    # Set the jobs into brigade and return the gateway info for each.
    createProjects(jobs)

    # Set our predict var
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

