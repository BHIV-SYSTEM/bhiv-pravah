# Deployment Proof

Validated steps:

- docker compose up -d
- docker compose ps
- docker compose restart
- health checks on the backend API
- readiness validation via the recovery validator

Observed proof log:

```text
## docker compose up -d
docker : time="2026-05-30T12:15:51+05:30" level=warning msg="C:\\Users\\spal4\\
OneDrive\\Desktop\\SHIVAM\\BHIV\\multi-agent-control-plane-main\\docker-compose
.yml: the attribute `version` is obsolete, it will be ignored, please remove 
it to avoid potential confusion"
At line:1 char:108
+ ... compose up -d" | Set-Content $log; (docker compose up -d 2>&1 | Out-S ...
+                                         ~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : NotSpecified: (time="2026-05-3...tial confusion" 
   :String) [], RemoteException
    + FullyQualifiedErrorId : NativeCommandError
 
 Container cicd-redis Running 
 Container cicd-deploy-worker-1 Running 
 Container cicd-agents Running 
 Container cicd-deploy-worker-2 Running 
 Container cicd-deploy-worker-3 Running 
 Container cicd-queue-monitor Running 
 Container cicd-health-monitor Running 
 Container cicd-redis Waiting 
 Container cicd-redis Waiting 
 Container cicd-redis Healthy 
 Container cicd-redis Healthy 


## docker compose ps
docker : time="2026-05-30T12:15:52+05:30" level=warning msg="C:\\Users\\spal4\\
OneDrive\\Desktop\\SHIVAM\\BHIV\\multi-agent-control-plane-main\\docker-compose
.yml: the attribute `version` is obsolete, it will be ignored, please remove 
it to avoid potential confusion"
At line:1 char:216
+ ... ocker compose ps" | Add-Content $log; (docker compose ps 2>&1 | Out-S ...
+                                            ~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : NotSpecified: (time="2026-05-3...tial confusion" 
   :String) [], RemoteException
    + FullyQualifiedErrorId : NativeCommandError
 
NAME                   IMAGE                                            COMMAND                  SERVICE           CREATED          STATUS                    PORTS
cicd-agents            multi-agent-control-plane-main-agents            "python -m control_pGǪ"   agents            35 minutes ago   Up 31 minutes (healthy)   5000/tcp, 8080/tcp, 8501/tcp
cicd-deploy-worker-1   multi-agent-control-plane-main-deploy-worker-1   "python -m control_pGǪ"   deploy-worker-1   35 minutes ago   Up 31 minutes (healthy)   5000/tcp, 8080/tcp, 8501/tcp
cicd-deploy-worker-2   multi-agent-control-plane-main-deploy-worker-2   "python -m control_pGǪ"   deploy-worker-2   35 minutes ago   Up 31 minutes (healthy)   5000/tcp, 8080/tcp, 8501/tcp
cicd-deploy-worker-3   multi-agent-control-plane-main-deploy-worker-3   "python -m control_pGǪ"   deploy-worker-3   35 minutes ago   Up 31 minutes (healthy)   5000/tcp, 8080/tcp, 8501/tcp
cicd-health-monitor    multi-agent-control-plane-main-health-monitor    "python -m monitorinGǪ"   health-monitor    35 minutes ago   Up 31 minutes (healthy)   5000/tcp, 8080/tcp, 8501/tcp
cicd-queue-monitor     multi-agent-control-plane-main-queue-monitor     "python -m monitorinGǪ"   queue-monitor     35 minutes ago   Up 31 minutes (healthy)   5000/tcp, 8080/tcp, 8501/tcp
cicd-redis             redis:7-alpine                                   "docker-entrypoint.sGǪ"   redis             45 minutes ago   Up 31 minutes (healthy)   0.0.0.0:6379->6379/tcp, [::]:6379->6379/tcp


## docker compose restart
docker : time="2026-05-30T12:15:52+05:30" level=warning msg="C:\\Users\\spal4\\
OneDrive\\Desktop\\SHIVAM\\BHIV\\multi-agent-control-plane-main\\docker-compose
.yml: the attribute `version` is obsolete, it will be ignored, please remove 
it to avoid potential confusion"
At line:1 char:326
+ ... ose restart" | Add-Content $log; (docker compose restart 2>&1 | Out-S ...
+                                       ~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : NotSpecified: (time="2026-05-3...tial confusion" 
   :String) [], RemoteException
    + FullyQualifiedErrorId : NativeCommandError
 
 Container cicd-queue-monitor Restarting 
 Container cicd-redis Restarting 
 Container cicd-health-monitor Restarting 
 Container cicd-agents Restarting 
 Container cicd-deploy-worker-3 Restarting 
 Container cicd-deploy-worker-2 Restarting 
 Container cicd-deploy-worker-1 Restarting 
 Container cicd-redis Started 
 Container cicd-agents Started 
 Container cicd-deploy-worker-2 Started 
 Container cicd-queue-monitor Started 
 Container cicd-health-monitor Started 
 Container cicd-deploy-worker-1 Started 
 Container cicd-deploy-worker-3 Started 


## docker compose ps (post-restart)
docker : time="2026-05-30T12:15:55+05:30" level=warning msg="C:\\Users\\spal4\\
OneDrive\\Desktop\\SHIVAM\\BHIV\\multi-agent-control-plane-main\\docker-compose
.yml: the attribute `version` is obsolete, it will be ignored, please remove 
it to avoid potential confusion"
At line:1 char:451
+ ... s (post-restart)" | Add-Content $log; (docker compose ps 2>&1 | Out-S ...
+                                            ~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : NotSpecified: (time="2026-05-3...tial confusion" 
   :String) [], RemoteException
    + FullyQualifiedErrorId : NativeCommandError
 
NAME                   IMAGE                                            COMMAND                  SERVICE           CREATED          STATUS                                     PORTS
cicd-agents            multi-agent-control-plane-main-agents            "python -m control_pGǪ"   agents            35 minutes ago   Up 1 second (health: starting)             5000/tcp, 8080/tcp, 8501/tcp
cicd-deploy-worker-1   multi-agent-control-plane-main-deploy-worker-1   "python -m control_pGǪ"   deploy-worker-1   35 minutes ago   Up Less than a second (health: starting)   5000/tcp, 8080/tcp, 8501/tcp
cicd-deploy-worker-2   multi-agent-control-plane-main-deploy-worker-2   "python -m control_pGǪ"   deploy-worker-2   35 minutes ago   Up Less than a second (health: starting)   5000/tcp, 8080/tcp, 8501/tcp
cicd-deploy-worker-3   multi-agent-control-plane-main-deploy-worker-3   "python -m control_pGǪ"   deploy-worker-3   35 minutes ago   Up Less than a second (health: starting)   5000/tcp, 8080/tcp, 8501/tcp
cicd-health-monitor    multi-agent-control-plane-main-health-monitor    "python -m monitorinGǪ"   health-monitor    35 minutes ago   Up Less than a second (health: starting)   5000/tcp, 8080/tcp, 8501/tcp
cicd-queue-monitor     multi-agent-control-plane-main-queue-monitor     "python -m monitorinGǪ"   queue-monitor     35 minutes ago   Up Less than a second (health: starting)   5000/tcp, 8080/tcp, 8501/tcp
cicd-redis             redis:7-alpine                                   "docker-entrypoint.sGǪ"   redis             45 minutes ago   Up 2 seconds (health: starting)            0.0.0.0:6379->6379/tcp, [::]:6379->6379/tcp
```

Recovery validation:

- ready: True
- status: READY
- replay_index_loaded: True
- state_hash: 1c951a1182ae58831ed5c29f5cd55d124828a38b3edd799f831920afcb977438
