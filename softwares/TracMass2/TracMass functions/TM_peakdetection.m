classdef TM_peakdetection < handle
    
    %Arguments: parent
    
    %by: Erik Tengstrand
    
    properties
        SampleList      
        Parameters
        CurrentTracker
        TrackerData
        RawData
        Chrom
        PeakList
        Detection
        MainPlot
        PeakData
        MaxTracker
        TimeUnit
        ParamListener
        param
    end
    
    
    events
        ProjectUpdate
        Update
    end
    
     methods
        
        function obj=TM_peakdetection(parent)
            
            HBoxHandle=uiextras.HBoxFlex('Parent',double(parent),'Spacing',5,'Padding',5);
            LeftBox=uiextras.VBox('Parent',double(HBoxHandle),'Spacing',5,'Padding',5);
            obj.SampleList=TM_samplelist(HBoxHandle);
            RightBox=uiextras.VBox('Parent',double(HBoxHandle),'Spacing',5,'Padding',5);
            set(HBoxHandle,'Sizes',[-1 -1 -3])
            
            %LeftBox
            obj.param=ParamPeakdetection;
            obj.Parameters=ParamPanel(obj.param,'Parent',double(LeftBox),'Title','Parameters');
            TM_ui(obj,LeftBox,'detection'); %three buttons
            uicontrol('Parent',double(LeftBox),'Style','PushButton','String','Load Samples','Callback',@(src,evt)obj.LoadSamples());
            uicontrol('Parent',double(LeftBox),'Style','PushButton','String','Process All Samples','Callback',@(src,evt)obj.ProcessAll());
            set(LeftBox,'Sizes',[-1 25 25 25 25 25])
            
            %right box
            obj.MainPlot=axes('Parent',double(RightBox));
            xlabel(obj.MainPlot,'Time (seconds)');
            ylabel(obj.MainPlot,'Intensity');
            NavigationPanel=uiextras.Panel('Parent',double(RightBox),'Title','Navigation','Padding', 1);
            set(RightBox,'Sizes',[-1 45])
            
            %Navigation panel
            Navigation=uiextras.HBox('Parent',double(NavigationPanel),'Spacing',0,'Padding',3);
            uicontrol('Parent',double(Navigation),'Style','PushButton','String','Previous PIC','Callback',@(src,evt)obj.PreviousTracker());
            obj.CurrentTracker=uicontrol('Parent',double(Navigation),'String',1,'Style','Edit','Callback',@(src,evt)obj.PlotCurrent());
            uicontrol('Parent',double(Navigation),'Style','PushButton','String','Next PIC','Callback',@(src,evt)obj.NextTracker());
            
            %listener
            obj.ParamListener=addlistener(obj.param,'ParamChange',@(src,evt)obj.PlotCurrent());
            addlistener(obj.SampleList,'ChangeSample',@(src,evt)obj.ChangeSample());
            addlistener(obj,'Update',@(src,evt)obj.PlotCurrent());
            addlistener(obj.SampleList,'Finished',@(src,evt)obj.LoadFiles());
        end
        
        function LoadSamples(obj)
            FileChooser(obj.SampleList,'*.PIC');
        end
        
        function LoadFiles(obj)
            set(obj.SampleList.ListBox,'String',obj.SampleList.Samples)
        end
        
        %checks outfolder and sends task to external function
        function ProcessAll(obj)
            PathOut=[obj.SampleList.ProjectPath filesep 'peak'];
            if ~isdir(PathOut)
                mkdir(obj.SampleList.ProjectPath,'peak')
            end
            
            files=obj.SampleList.SamplePath;
            if iscell(files)
                iSamp=numel(files);
                for N=1:numel(files);
                    [~, SampleName]=fileparts(files{N});
                    PeakFile=fullfile(obj.SampleList.ProjectPath,'peak',[SampleName '.peak']);
                    if exist(PeakFile,'file')==2
                        ProcessedParam=load(char(PeakFile),'-mat','param');
                        isEq=ParamCmp(obj.Parameters.param,ProcessedParam.param);
                        if isEq==1
                            iSamp(N)=0;
                        end
                    end
                end
                files(iSamp==0)=[];
            end
            
            TMpeakDetectZAF2(files,PathOut,obj.Parameters.param,obj.SampleList.ProjectPath); %external function
            notify(obj,'ProjectUpdate')
        end
        
        %when a new sample is selected in the sample list, this function is
        %called
        function ChangeSample(obj)
            cla(obj.MainPlot);
            set(obj.CurrentTracker,'Value',1);
            set(obj.CurrentTracker,'string',1);
            TheFile=obj.SampleList.SamplePath(obj.SampleList.CurrentSample);
            obj.TrackerData=load(char(TheFile),'-mat');
            obj.RawData=LoadRawDataV3(obj.TrackerData.rawFile,obj.SampleList.ProjectPath);
            if strcmp(obj.RawData.info.unit,'seconds')
                obj.TimeUnit=1;
            else 
                obj.TimeUnit=1/60;
            end
            
            PeakFile=fullfile(obj.SampleList.ProjectPath,'peak',[obj.SampleList.Samples{obj.SampleList.CurrentSample} '.peak']);
            if exist(PeakFile,'file')==2
                ProcessedParam=load(PeakFile,'-mat','param');
                obj.Parameters.param=ProcessedParam.param;
                obj.Parameters.refresh
                addlistener(obj.Parameters.param,'ParamChange',@(src,evt)obj.PlotCurrent());
            end
            
            %determines scantime(dt) from the first sample loaded, and
            %since f is depentent on dt it must also be reevaluated.
            if obj.Parameters.param.dt<0
                obj.Parameters.param.dt=median(diff(obj.RawData.time_axis));
                if obj.Parameters.param.dt/obj.Parameters.param.gaussWidth>obj.Parameters.param.gaussSigma
                    obj.Parameters.param.gaussSigma=obj.Parameters.param.dt/obj.Parameters.param.gaussWidth*1.01;
                end
                obj.Parameters.param.f=CalibrateStandardFilter(obj.Parameters.param);
            end
            
            obj.MaxTracker=max(obj.TrackerData.trackerData(:,1));
            obj.PlotTracker;
            obj.PlotDetection;
        end
        
        %The three functions for selecting the tracker
        function PlotCurrent(obj)
            delete(obj.ParamListener);
            obj.ParamListener=addlistener(obj.Parameters.param,'ParamChange',@(src,evt)obj.PlotCurrent());
            Current=str2double(get(obj.CurrentTracker,'String'));
            if isnan(Current)
                Current=1;
            end
            if Current > obj.MaxTracker
                Current=obj.MaxTracker;
            end
            if Current<1
                Current=1;
            end
            set(obj.CurrentTracker,'Value',Current);
            set(obj.CurrentTracker,'String',Current);
            obj.PlotTracker;
            obj.PlotDetection;
        end
        
        function PreviousTracker(obj)
            Current=get(obj.CurrentTracker,'Value');
            if Current<2
                Current=2;
            end
            set(obj.CurrentTracker,'Value',Current-1);
            set(obj.CurrentTracker,'String',num2str(Current-1));
            obj.PlotTracker;
            obj.PlotDetection;
        end
        
        function NextTracker(obj)
            Current=get(obj.CurrentTracker,'Value');
            if Current>obj.MaxTracker
                Current=obj.MaxTracker-1;
            end
            set(obj.CurrentTracker,'Value',Current+1);
            set(obj.CurrentTracker,'String',num2str(Current+1));
            obj.PlotTracker;
            obj.PlotDetection;
        end
        
        %the two functions for plotting peak detection and tracker, called by many of the other
        %functions
        function PlotTracker(obj)
            cla(obj.MainPlot)
            trackNo=get(obj.CurrentTracker,'Value');
            Mask=obj.TrackerData.trackerData(:,1)==trackNo;
            obj.Chrom.time=obj.RawData.time_axis(obj.TrackerData.trackerData(Mask,3));
            obj.Chrom.intensity=obj.RawData.intensity_values(obj.TrackerData.trackerData(Mask,2));
            obj.Chrom.mass=obj.RawData.mass_values(obj.TrackerData.trackerData(Mask,2));
            plot(obj.MainPlot,obj.Chrom.time/obj.TimeUnit,obj.Chrom.intensity);
            xlabel(obj.MainPlot,'Time (seconds)');
            ylabel(obj.MainPlot,'Intensity');
            mass=mean(obj.RawData.mass_values(obj.TrackerData.trackerData(Mask,2)));
            title(obj.MainPlot,sprintf('%g m/z',mass))
        end
        
        function PlotDetection(obj)
            hold(obj.MainPlot,'on')
            [obj.PeakList,obj.Detection] = peakDetectChrom(obj.Chrom,obj.Parameters.param);
            obj.Detection.time=obj.Detection.time/obj.TimeUnit;
            h2=plot(obj.MainPlot,obj.Detection.time,obj.Detection.xs,'k:');
            h3=plot(obj.MainPlot,obj.Detection.time,obj.Detection.z1,'g');
            h4=plot(obj.MainPlot,obj.Detection.time,obj.Detection.z2,'c');
            h5=plot(obj.MainPlot,obj.Detection.time,obj.Detection.err,'r:');
            h1=plot(obj.MainPlot,obj.PeakList.time/obj.TimeUnit,obj.PeakList.intensity,'ro');
            if numel(obj.PeakList.intensity)>0
                legend([h1 h2 h3 h4 h5],'Detected peak','Smoothed data','ZAF 1','ZAF 2','Estimated noise')
            else
                legend([h2 h3 h4 h5],'Smoothed data','ZAF 1','ZAF 2','Estimated noise')
            end
            set_nice_axis;
        end
        
     end
end