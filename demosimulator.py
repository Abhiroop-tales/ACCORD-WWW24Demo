from googleapiclient.http import MediaInMemoryUpload
from serviceAPI import create_simulator_driveAPI_service
from extractSimulatorList import getFileList, getFolderList, getUserList
import random, base64, time
from datetime import datetime
from googleapiclient.errors import HttpError
from sqlconnector import DatabaseQuery


# Class to initialize a user subject to perform actions
class UserSubject():
    def __init__(self, user_name, user_dict):
        self.userName = user_name

        # Create DriveAPI service for the user and fetch the file List, folder List and the target user List
        
        self.service = create_simulator_driveAPI_service(user_dict[user_name])
        totalList = list(user_dict.keys())
        totalList.remove(user_name)
        self.usersList = totalList
        self.userEmail = self.userName

    def fetch_file(self):
        # Initialize an empty dictionary to store file names and IDs
        files_dict = {}

        try:
            # Call the Drive API to list the files
            # Modify pageSize as needed; here it's set to 100 to fetch up to 100 files
            results = self.service.files().list(
                pageSize=100,
                fields="nextPageToken, files(id, name)"
            ).execute()
            
            # Get the list of files
            files = results.get('files', [])
            
            # Populate the dictionary with file names and file IDs
            for file in files:
                files_dict[file['name']] = file['id']
            
        except Exception as e:
            print(f"An error occurred: {e}")
            return None
        
        return files_dict


# Class to perform actions individually
class PerformActions():
    def __init__(self, owner, actor, action, actionType, fileID, actionIndex, constraintAction):
        self.action = action
        self.userSubject = actor
        self.actionType = actionType
        self.fileID = fileID
        self.ownerName = owner
        self.actionCount = 1
        self.actionIndex = actionIndex
        self.constraintAction = constraintAction

    # Check permissions to Edit and share the file
    def check_permissions(self, fileID):
        try:
            file = self.userSubject.service.files().get(fileId=fileID, fields="permissions").execute()
            email = self.userSubject.userEmail  # Make sure you are using the correct attribute for the user's email
            can_edit = False
            for permission in file['permissions']:
                if(email == permission.get('emailAddress') and permission.get('role') in ['writer', 'owner']):
                    can_edit = True
                    break
            return can_edit
        except HttpError as error:
            return False
        
    
    # Simulate Permission Change actions
    def simulate_permissionChange(self, actionType):
        
        fileUserList, userIdList = getUserList(self.userSubject.service, self.fileID)
        roles = ['writer', 'commenter', 'reader'] 
        fileID = self.fileID
        if(self.check_permissions(fileID)):
            print(actionType)
            #########################
            match actionType:
                # Add User to the file
                case "Add Permission":
                    new_userList = list(set(self.userSubject.usersList).difference(fileUserList))
                    newUser = random.choice(new_userList)

                    
                    
                    if new_userList:
                        permission = {
                            'type': 'user',
                            'role': 'writer',
                            'emailAddress': newUser
                        }
                        self.userSubject.service.permissions().create(fileId=fileID, body=permission, sendNotificationEmail=False).execute()
                        return True

                case "Remove Permission":
                    # Remove the actor ID from the user ID list and choose a random user to remove permission
                    
                    userIdList.pop(fileUserList.index(self.userSubject.userName))
                    if userIdList:
                        # Fetch the permissions for the file
                        permissions = self.userSubject.service.permissions().list(fileId=fileID).execute()

                        # Filter the permissions to exclude the owner
                        non_owner_permissions = [
                            permission for permission in permissions.get("permissions", [])
                            if permission.get("role") != "owner" and permission.get("id") in userIdList
                        ]

                        # If there are non-owner permissions, remove a random one
                        if non_owner_permissions:
                            random_permission = random.choice(non_owner_permissions)
                            self.userSubject.service.permissions().delete(
                                fileId=fileID, permissionId=random_permission["id"]
                            ).execute()
                            return True


                case "Update Permission":
                    # Remove the actor ID from the user ID list and choose a random user to update permission
                    
                    userIdList.pop(fileUserList.index(self.userSubject.userName))
                    if userIdList:
                        # Fetch the permissions for the file
                        permissions = self.userSubject.service.permissions().list(fileId=fileID).execute()
                        
                        # Filter the permissions to exclude the owner
                        non_owner_permissions = [
                            permission for permission in permissions.get("permissions", [])
                            if permission.get("role") != "owner" and permission.get("id") in userIdList
                        ]

                        # If there are non-owner permissions, remove a random one
                        if non_owner_permissions:
                            userID = random.choice(non_owner_permissions)['id']
                            permission = self.userSubject.service.permissions().get(fileId=fileID, permissionId = userID).execute()
                            user_role = [permission['role']]
                            new_user_role = random.choice(list(set(roles).difference(user_role)))
                            new_permission = {'role' : new_user_role }
                            self.userSubject.service.permissions().update(fileId=fileID, permissionId = userID, body=new_permission).execute()
                            return True

                
                case _:
                    pass
        
        return False
    
    # Simulate Edit action 
    def simulate_edit(self):
        fileID = self.fileID
        file = self.userSubject.service.files().get(fileId=fileID).execute()
        mime_type = file['mimeType']

        # Check if file is of Document Type
        if(mime_type == 'application/vnd.google-apps.document'):
         
            fileContent = "Hello World! File has been Edited on " + str(datetime.now())
            encoded_content = base64.b64encode(fileContent.encode())
            decoded_content = base64.b64decode(encoded_content).decode()
            media = MediaInMemoryUpload(decoded_content.encode(), mimetype=mime_type)
            file = self.userSubject.service.files().update(fileId=fileID, media_body=media).execute()
            return True

        return False
    
    # Simulate Move Action
    def simulate_move(self, folderList):
        fileID = self.fileID
              
        # Retrieve the current parent(s) of the file
        file = self.userSubject.service.files().get(fileId=fileID, fields='parents').execute()
        if file:
            previous_parents = ",".join(file['parents'])
            old_parents_list = file['parents']
            total_FolderList = folderList
            new_FolderList = list(set(total_FolderList).difference(old_parents_list))
            if new_FolderList and fileID not in new_FolderList:
                # Move the file to the new folder
                newFolder = random.choice(new_FolderList)
                self.userSubject.service.files().update(fileId=fileID, addParents=newFolder, removeParents=previous_parents, fields='id, parents').execute()
                return True
        
        return True

            
        
    
    # Simulate Delete Action
    def simulate_delete(self):
        fileID = self.fileID
        if(self.check_permissions(fileID)):
            self.userSubject.service.files().delete(fileId=fileID).execute()
            return True
        
        return False
    
    # Simulate Create Action
    def simulate_create(self, inFolder):
        # Define the file metadata
        total_FolderList = getFolderList(self.userSubject.service)
        fruitNames = ["apple", "banana", "cherry", "date", "elderberry", "fig", "grape", "honeydew", "kiwi", "lemon", "orange", "peach", "pear", "pineapple", "strawberry", "watermelon", "london", "paris", "newyork", "tokyo", "berlin", "mumbai", "report", "document", "presentation", "spreadsheet", "invoice", "receipt"]
        file_metadata = {
            'name': random.choice(fruitNames) + '_' + datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + '.docx',
            'mimeType': 'application/vnd.google-apps.document'
            }
        if(inFolder):
            file_metadata['parents'] = [random.choice(total_FolderList)]
        
        fileID = self.userSubject.service.files().create(body=file_metadata, media_body=None).execute()
        self.fileID = fileID.get('id')
        return True
    
    # Method to perform actions based on the Selected options
    def perform_actions(self, actorsDict):
        try:
            actorList = list(actorsDict.keys())

            # Always make sure first permission change is additon of people
            actor = self.ownerName

            # Perform actions until the action Count parameters is zero
            while(self.actionCount > 0):
                simval = False
                # Choose an actor and an action

                action = self.action              
                
                fileList = getFileList(self.userSubject.service)
                folderList = getFolderList(self.userSubject.service)

                
                print("################################")
                print(action)
             
                # Simulate Actions based on action selected
                match action:
                    case "Create":
                        
                        simval = self.simulate_create(False)

                    case "Delete":
                        #file_object = self.fileobject
                        simval =self.simulate_delete()
                        if(simval):
                            self.fileID = 'None'
                    
                    case "Edit":
                        simval = self.simulate_edit()

                    case "Move":
                        #file_object = self.fileobject
                        simval = self.simulate_move(folderList)
                    
                    case "Permission Change":
                        #file_object = self.fileobject
                        if(self.actionIndex <3):
                            actionType = "Add Permission"                                 
                        elif(self.actionIndex == 3 and self.action == "Permission Change"):
                            actionType = self.actionType
                        else:
                            actionTypes = ['Add Permission', 'Remove Permission', 'Update Permission']
                            actionType = random.choice(actionTypes)
                            
                        
                        simval = self.simulate_permissionChange(actionType)
                                               
                    
                    case _:
                        pass
                        
                
                if(simval):
                    #print(action)
                    
                    self.actionCount -= 1
                    time.sleep(2)

                
            
            return self.fileID

        except LookupError as le:
            return("Error in the key or index !!\n" + str(le))
        except ValueError as ve:
            return("Error in Value Entered !!\n" + str(ve))
        except TypeError as te:
            return("Error in Type matching !!\n" + str(te))  