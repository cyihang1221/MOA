classdef TM_database < handle
    
    %by: Erik Tengstrand and Magnus Åberg
    
    properties
        peakList
        sample
        
        Cluster1ID
        Cluster2ID
        HoughID
        WarpedTime
        
        Time
        coeffs
        meanTime
        theGCV
        xNice
        BNice
        bSplineRange
    end
    
    methods
        function obj=TM_database(samplelist,param)
            timeLim=[param.StartTime param.EndTime];
            massLim=[param.MinMZ param.MaxMZ];
            intensityLim=param.IntensityThreshold;
            
            files=samplelist.SamplePath;
            
            k = 0;
            for i = 1:numel(files)
                [~,name] = fileparts(files{i});
                peakFile=samplelist.SamplePath{i};
                F = load('-mat',peakFile,'rawFile');
                rawFile=F.rawFile;
                F = load('-mat',peakFile,'picFile');
                picFile=F.picFile;
                
                db.sample.id(i,1) = i;
                db.sample.name{i,1} = name;
                db.sample.rawFile{i,1}  = rawFile;
                db.sample.picFile{i,1} = picFile;
                
                peakid=load('-mat',peakFile,'id');
                k = k + numel(peakid.id);
            end
            

            
            
            nPeaks = k;
            
            db.peakList.sample = zeros(nPeaks,1);
            db.peakList.pic = zeros(nPeaks,1);
            db.peakList.id = zeros(nPeaks,1);
            db.peakList.time = zeros(nPeaks,1);
            db.peakList.mass = zeros(nPeaks,1);
            db.peakList.intensity = zeros(nPeaks,1);
            db.peakList.width = nan(nPeaks,1);
            db.peakList.massStd = nan(nPeaks,1);
            
            db.sample.peakFile = cell(size(db.sample.id));
            
            nPeaks = 0;
            for i = 1:numel(db.sample.id)
                picFile = db.sample.picFile{i,1};
                peakFile = files{i};
                db.sample.peakFile{i} = peakFile;
                try
                    peak = load('-MAT',peakFile);
                catch
                    disp(sprintf('File: "%s" is missing.',peakFile));
                    continue
                end
                
                load('-MAT',picFile,'trackerData');
                
                mask = peak.time>=timeLim(1) & peak.time<=timeLim(2) & ...
                    peak.mass>=massLim(1) & peak.mass<=massLim(2) & ...
                    peak.intensity >= intensityLim;
                
                peak = maskTable(peak,mask);
                
                kPeaks = numel(peak.id);
                %disp([i kPeaks]);
                
                inds = nPeaks+(1:kPeaks);
                nPeaks = nPeaks+kPeaks;
                
                db.peakList.sample(inds) = db.sample.id(i);
                db.peakList.pic(inds)= peak.pic;
                if isfield(peak,'id')
                    db.peakList.id(inds) = peak.id;
                else
                    db.peakList.id(inds) = (1:kPeaks)';
                end
                db.peakList.time(inds)      = peak.time/peak.TimeUnit;
                db.peakList.mass(inds)      = peak.mass;
                db.peakList.intensity(inds) = peak.intensity;
                
                if isfield(peak,'width')
                    db.peakList.width(inds) = peak.width;
                end
                if isfield(peak,'massStd')
                    db.peakList.massStd(inds) = peak.massStd;
                end
            end
            
            db.peakList = maskTable(db.peakList,db.peakList.sample ~= 0);
            obj.sample=db.sample;
            obj.peakList=db.peakList;
        end
    end
end