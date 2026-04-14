function TrackSamples(files,projectpath,parameters)

%by: Magnus Åberg and Erik Tengstrand

Nmax=numel(files);

WaitTotal=Nmax;
ProgressHandle=waitbar(0,'Processing samples','CreateCancelBtn','setappdata(gcbf,''canceling'',1)');
setappdata(ProgressHandle,'canceling',0)
try
for N=1:Nmax

    [~,filename,ext]=fileparts(files{N});

    raw=LoadRawDataV3(files{N},projectpath);
    
    raw=subsetRawData(raw,[parameters.timeRange parameters.mzRange]);
    raw=thresholdRawData(raw,parameters.rawData_threshold);
    trackers=nnFastTrack(raw,parameters);
    trackers=trackerFilter05(trackers,raw,parameters);
    trackers=renumberTrackers(trackers);
    summary=tracker_summary2(trackers,raw);
    
    ts = sortTable(summary,'intensity','descend');
    II = (1:numel(ts.intensity))';
    [~,order] = sort(ts.ID);
    II = II(order);
    c = getCounts(trackers(:,1),[1:max(trackers(:,1))]');
    nds = [0; cumsum(c)];
    for i = 1:numel(c)
        trackers(nds(i)+(1:c(i)),1)=II(i);
    end
    summary = ts;
    summary.ID = 1:numel( ts.ID );
   
    %save
    savefile=fullfile(projectpath,'pic',[filename,'.pic']);
    if ~isdir([projectpath filesep 'pic'])
        mkdir(projectpath,'pic')
    end
    saveData.trackerData=trackers;
    saveData.trackerSummary=summary;
    saveData.trackerData(:,2) = raw.points(saveData.trackerData(:,2));
    saveData.trackerData(:,3) = raw.scan_id(saveData.trackerData(:,3));
    saveData.rawFile = files{N};
    saveData.param=parameters;
    save(savefile,'-struct','saveData','-MAT')
    
    if getappdata(ProgressHandle,'canceling')
        fprintf('Process canceled: %i samples processed.\n',N)
        warndlg( sprintf('Process canceled: %i samples processed.',N),'Process canceled')
        break
    end
    waitbar(N/WaitTotal,ProgressHandle);
end
delete(ProgressHandle)
catch
    disp('Error: process incomplete')
    delete(ProgressHandle)
end
