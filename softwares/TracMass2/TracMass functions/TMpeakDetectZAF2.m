function TMpeakDetectZAF2(files,pthOut,param,projectPath)

%by Magnus Åberg
picFile = char(files(1));
pic = load('-mat',picFile);

WaitTotal=numel(files)+1;
ProgressHandle=waitbar(0,'Processing samples','CreateCancelBtn','setappdata(gcbf,''canceling'',1)');
setappdata(ProgressHandle,'canceling',0)

raw = LoadRawDataV3(pic.rawFile,projectPath);
param.dt=median(raw.time_axis(2:end)-raw.time_axis(1:(end-1)));

% create filters
zaf = mk_zaf(param.dt,param.zafSigma,param.zafWidth);
zaf2 =mk_zaf(param.dt,param.zaf2Sigma,param.zaf2Width);
gauss=mk_gauss(param.dt,param.gaussSigma,param.gaussWidth);

%s = randn('state');
%randn('state',314); %initialize the random number generator go get identical results each time
%param.f = calibrate_stdFilter(param.gauss,param.stdFiltWidth);
%param.f = calibrate_stdFilter3(param.gauss,param.stdFiltWidth);
%randn('state',s);




%printStatus4('clear')

try
for isamp = 1:numel(files)
    % set up files and check that peak detection has not already been done
    picFile = char(files(isamp));
    [foo,peakFile,ext] = fileparts(picFile);
    peakFile = fullfile(pthOut,[peakFile,'.peak']);
    
    % load data and start peak detecting.
    pic = load('-mat',char(picFile));
    rawFile = pic.rawFile;
    raw = LoadRawDataV3(rawFile,projectPath);
    nPics = numel(pic.trackerSummary.ID);
    peak.time = [];
    peak.mass = [];
    peak.intensity =[];
    peak.id =[];
    peak.pic =[];
    peakCnt =0;
    
    pic.trackerData = sortrows(pic.trackerData); %%
    
    [C,I,ref]=getCounts2(pic.trackerData(:,1)); %%
    for ipic = 1:nPics,
        %printStatus4('sample=%i(%i)\nPIC=%i(%i)\n',isamp,numel(files),ipic,nPics)
        
        %mask = pic.trackerData(:,1)==ipic; % old and slow
        inds  = I(ipic) + (1:C(ipic));
        achrom.intensity = raw.intensity_values(pic.trackerData(inds,2));
        achrom.time = raw.time_axis(pic.trackerData(inds,3));
        achrom.mass = raw.mass_values(pic.trackerData(inds,2));
        % peak detection
        inds =zafPeakDetect2_2(achrom.intensity(:),zaf,zaf2,gauss,param.stdFiltWidth,param.nSignalToNoise,param.f,false);
        %inds =zafPeakDetect2_2(achrom.intensity(:),param.zaf,param.zaf2,param.gauss,param.stdFiltWidth,param.nStd,param.f,true);
        
        pl =mkPeakList2(achrom,inds,gauss);
        
        n = numel(pl.intensity);
        inds = peakCnt+(1:n);
        peakCnt = peakCnt + n;
        peak.time(inds,1) = pl.time;
        peak.mass(inds,1) = pl.mass;
        peak.intensity(inds,1) = pl.intensity;
        peak.id(inds,1) = inds;
        peak.pic(inds,1) = ipic;
    end
    
    peak.picFile = picFile;
    peak.rawFile = rawFile;
    peak.param=param;
    if strcmp(raw.info.unit,'seconds')
        peak.TimeUnit=60;
    else
        peak.TimeUnit=1;
    end
    save(peakFile,'-struct','peak','-mat');
    %save([peakFile,'.param'],'-struct','param','-mat')
    
    if getappdata(ProgressHandle,'canceling')
        fprintf('Process canceled: %i samples processed.\n',isamp )
        warndlg( sprintf('Process canceled: %i samples processed.',isamp ),'Process canceled')
        break
    end
    
    waitbar(isamp/WaitTotal,ProgressHandle);
end
delete(ProgressHandle)
catch
    delete(ProgressHandle)
    disp('Error: process incomplete')
end


