classdef TM_tracker < handle
    
    %Arguments: parent
    
    %by: Erik Tengstrand
    
    properties
        Parameters   
        SideData     %the data used by the plot for single trackers
        SampleList   
        rawdata
        
        MainPlot     %handle for the upper right plot, used for plotting an entire sample
        SidePlot     %handle for the lower right plot, used for plotting a single tracker
        
        %these are used for marking and plotting single trackers
        last
        tracker_data
        summary
        x_range
        y_range
        VisibleTracker_Handle
        ZoomData
        GreyHandle
        CurrentTracker
        Type='INT';
        MaxTracker
        Visible
        
        MZmargin=0.2;
        TimeMargin=0.5;
        time=1;
        TrackerRestriction=1000;
    end
    
    
    events
        ProjectUpdate
        Update
        Samples
    end
    
    methods
        
        function obj=TM_tracker(parent)
            
            HBox=uiextras.HBoxFlex('Parent',double(parent),'Spacing',5,'Padding',5);
            
            LeftBox=uiextras.VBox('Parent',double(HBox),'Spacing',5,'Padding',5);
            obj.SampleList=TM_samplelist(HBox); %samplelist in the middle box
            RightBox=uiextras.VBoxFlex('Parent',double(HBox),'Spacing',5,'Padding',5);
            set(HBox,'Sizes',[-1.3 -1 -3]);
            
            %parameterpanel and buttons in the middle box
            param=ParamTracking;
            obj.Parameters=ParamPanelTracking(param,LeftBox); %creates the parameter panel, and adds a popup menu
            TM_ui(obj,LeftBox,'tracker'); %three buttons
            uicontrol('Parent',double(LeftBox),'Style','PushButton','String','Load Samples','Callback',@(src,evt)obj.LoadSamples());
            uicontrol('Parent',double(LeftBox),'Style','PushButton','String','Process Visible','Callback',@(src,evt)obj.ProcessVisible());
            uicontrol('Parent',double(LeftBox),'Style','PushButton','String','Process Selected Samples','Callback',@(src,evt)obj.ProcessSelected());
            uicontrol('Parent',double(LeftBox),'Style','PushButton','String','Process All Samples','Callback',@(src,evt)obj.ProcessAll());
            set(LeftBox,'Sizes',[-1 25 25 25 25 25 25 25])
            
            %right box, displays the trackers for validation
            obj.MainPlot=axes('Parent',double(RightBox)); %plot for all trackers
            z=zoom;
            set(z,'ActionPostCallback',@(src,evt)obj.postZoom());
            xlabel(obj.MainPlot,'Time (minutes)');
            ylabel(obj.MainPlot,'m/z');
            LowerBox=uiextras.VBox('Parent',double(RightBox),'Spacing',5,'Padding',5);
            set(RightBox,'Sizes',[-3 -2]);
            obj.SidePlot=axes('Parent',double(LowerBox)); %plot for a single tracker
            
            %buttons for changeing the single tracker plot between m/z and
            %intensity
            LowerHBox=uiextras.HBox('Parent',double(LowerBox),'Spacing',5,'Padding',5);
            uicontrol('Parent',double(LowerHBox),'Style','PushButton','String','Intensity vs. Time','Callback',@(src,evt)obj.plotINT());
            uicontrol('Parent',double(LowerHBox),'Style','PushButton','String','M/Z vs. Time','Callback',@(src,evt)obj.plotMZ());
                        
            %Navigation panel
            NavigationPanel=uiextras.Panel('Parent',double(LowerBox),'Title','Navigation','Padding',1);
            Navigation=uiextras.HBox('Parent',double(NavigationPanel),'Spacing',0,'Padding',4);
            uicontrol('Parent',double(Navigation),'Style','PushButton','String','Previous PIC','Callback',@(src,evt)obj.PreviousTracker());
            obj.CurrentTracker=uicontrol('Parent',double(Navigation),'String',1,'Style','Edit','Callback',@(src,evt)obj.PlotCurrent());
            uicontrol('Parent',double(Navigation),'Style','PushButton','String','Next PIC','Callback',@(src,evt)obj.NextTracker());
            
            set(LowerBox,'Sizes',[-1 35 50])
            
            %a listener for when a single sample is selected in the
            %samplelist
            addlistener(obj.SampleList,'ChangeSample',@(src,evt)obj.NewSample());
            addlistener(obj.SampleList,'Finished',@(src,evt)obj.LoadFiles());
            
        end
        
        function PreviousTracker(obj)
            CT=str2double(get(obj.CurrentTracker,'string'))-1;
            CT=max(CT,1);
            set(obj.CurrentTracker,'string',num2str(CT));
            obj.PlotCurrent;
        end
        
        function NextTracker(obj)
            CT=str2double(get(obj.CurrentTracker,'string'))+1;
            CT=min(CT,obj.MaxTracker);
            set(obj.CurrentTracker,'string',num2str(CT));
            obj.PlotCurrent;
        end
        
        % plots more raw data if an empty region is zoomed
        function postZoom(obj)
            if gca==obj.MainPlot
            try
                delete(obj.ZoomData)
            end
            try 
                delete(obj.GreyHandle)
            end
            xrange=get(obj.MainPlot,'XLim')*obj.time;
            yrange=get(obj.MainPlot,'YLim');
            VisibleSubset=subsetRawData(obj.rawdata,xrange,yrange);
            threshold1=prctile(VisibleSubset.intensity_values,99);
            sortedInts=sort(VisibleSubset.intensity_values,1,'descend');
            if numel(sortedInts)>500
                threshold=min(threshold1,sortedInts(500));
            else
                threshold=sortedInts(end);
            end
            hold(obj.MainPlot,'on')
            if threshold~=threshold1;
                NumSortInt=numel(sortedInts);
                prct20=sortedInts(round(0.8*NumSortInt):NumSortInt);
                Grey=min((max(prct20)+10*std(prct20)),threshold1);
                Grey=max(Grey,prctile(VisibleSubset.intensity_values,90));
                threshold=Grey;
                GreyInds=VisibleSubset.intensity_values<Grey;
                VisibleTime=getRawTime(VisibleSubset)/obj.time;
                obj.GreyHandle=plot(obj.MainPlot,VisibleTime(GreyInds),VisibleSubset.mass_values(GreyInds),'.','Color',[0.8 0.8 0.8],'MarkerSize',4);
                set(obj.GreyHandle,'ButtonDownFcn',@(src,evt)obj.ClosestTracker())
            end
            threshold_data=thresholdRawData(VisibleSubset,threshold);
            obj.ZoomData=plotRawData2(obj.MainPlot,threshold_data,'Minutes',obj.time);
            set(obj.ZoomData,'ButtonDownFcn',@(src,evt)obj.ClosestTracker())
            hold(obj.MainPlot,'off')
            set(obj.MainPlot,'XLim',xrange/obj.time)
            set(obj.MainPlot,'YLim',yrange)
            
            end
        end
        
        
        %Tracks all the data visible in the main plot. If there are more
        %than 1000 trackers, trackers will only be plotted as lines
        function ProcessVisible(obj)
            cla(obj.SidePlot)
            xlabel(obj.SidePlot,'Time (minutes)');
            ylabel(obj.SidePlot,'Intensity');
            
            for N=1:numel(obj.VisibleTracker_Handle)
                delete(obj.VisibleTracker_Handle(N))
            end
            obj.VisibleTracker_Handle=[];
            obj.x_range=get(obj.MainPlot,'XLim')*obj.time;
            obj.y_range=get(obj.MainPlot,'YLim');
            VisibleSubset=subsetRawData(obj.rawdata,obj.x_range,obj.y_range);
            VisibleSubset=thresholdRawData(VisibleSubset,obj.Parameters.param.rawData_threshold);
            obj.Visible=VisibleSubset;
            subset_tracker=nnFastTrack( VisibleSubset, obj.Parameters.param );
            trackerData = trackerFilter05( subset_tracker, VisibleSubset, obj.Parameters.param );
            if numel(trackerData)<3
                obj.MaxTracker=0;
                return
            end
                
            trackerData = renumberTrackers(trackerData);
            [trackerData, obj.summary]= sortTrackers(trackerData,VisibleSubset);
            obj.tracker_data=trackerData;
            hold(obj.MainPlot,'on')
            obj.MaxTracker=max(trackerData(:,1));
            TrackVector=1:obj.MaxTracker;
            
            %limit amount of trackers for speed
            if obj.MaxTracker>obj.TrackerRestriction
                for N=1:obj.MaxTracker
                    tracker=obj.tracker_data(:,1)==N;
                    mz=mean(obj.Visible.mass_values(obj.tracker_data(tracker,2)));
                    timevalues=obj.Visible.time_axis(obj.tracker_data(tracker,3))/obj.time;
                    obj.VisibleTracker_Handle(N)=plot(obj.MainPlot,[min(timevalues) max(timevalues)],[mz mz],'r-','LineWidth', 1);
                    set(obj.VisibleTracker_Handle(N),'ButtonDownFcn', @(src,evt)obj.MarkTracker(N));
                end
            else
                for N=TrackVector
                    tracker=trackerData(:,1)==N;
                    mzvalues=obj.Visible.mass_values(trackerData(tracker,2));
                    timevalues=obj.Visible.time_axis(trackerData(tracker,3))/obj.time;
                    obj.VisibleTracker_Handle(N)=plot(obj.MainPlot,timevalues,mzvalues,'r-','LineWidth', 1);
                    set(obj.VisibleTracker_Handle(N),'ButtonDownFcn', @(src,evt)obj.MarkTracker(N));
                end
            end
                        
            hold(obj.MainPlot,'off')
            set(obj.CurrentTracker,'string','1')
            obj.PlotCurrent
        end
        
%         Now done by PlotCurrent
%           %if a tracker in the main plot is clicked, this function is called
%           %to mark that tracker and to plot it in the smaller plot below the
%           %main plot.
        function MarkTracker(obj,N)
            set(obj.CurrentTracker,'string',num2str(N))
            obj.PlotCurrent
        end
        
        function ClosestTracker(obj)
            C=get(obj.MainPlot,'CurrentPoint');
            T=C(1,1)*obj.time;
            inds=find(T>obj.summary.timeStart & T<obj.summary.timeStop);
            [~, mzind]=min(abs(obj.summary.mz(inds)-C(1,2)));
            N=obj.summary.ID(inds(mzind));
            if ~isempty(N)
                MarkTracker(obj,N)
            end
        end
        
        function PlotCurrent(obj)
            try
                set(obj.last,'color',[0.7 0 0]) %the last marked is marked dark red
            end
            CT=str2double(get(obj.CurrentTracker,'string'));
            if isnan(CT)
                CT=1;
            end
            if CT>obj.MaxTracker
                CT=obj.MaxTracker;
            end
            if CT<1
                CT=1;
            end
            set(obj.CurrentTracker,'string',CT)
            if obj.MaxTracker==0
                return
            end
            obj.last=obj.VisibleTracker_Handle(CT);
            set(obj.last,'LineWidth',2,'color',[0 .7 0])
            tracker=obj.tracker_data(:,1)==CT;
            obj.SideData.MZ=obj.Visible.mass_values(obj.tracker_data(tracker,2));
            obj.SideData.Time=obj.Visible.time_axis(obj.tracker_data(tracker,3))/obj.time;
            obj.SideData.INT=obj.Visible.intensity_values(obj.tracker_data(tracker,2));
            
            mz_limit=[(min(obj.SideData.MZ)-obj.MZmargin) (max(obj.SideData.MZ)+obj.MZmargin)];
            time_limit=[(min(obj.SideData.Time)-obj.TimeMargin) (max(obj.SideData.Time)+obj.TimeMargin)];
            tracker_subset=subsetRawData(obj.rawdata,time_limit*obj.time,mz_limit);
            obj.SideData.AllTime=getRawTime(tracker_subset)/obj.time;
            obj.SideData.AllMZ=tracker_subset.mass_values;
            obj.SideData.AllINT=tracker_subset.intensity_values;
            
            switch obj.Type
                case 'INT'
                    obj.plotINT
                case 'MZ'
                    obj.plotMZ
            end
            hold(obj.SidePlot,'off');
        end
        
        %changes the single tracker plot to intensity vs time
        function plotINT(obj)
            obj.Type='INT';
            cla(obj.SidePlot,'reset')
            hold(obj.SidePlot,'on')
            plot(obj.SidePlot,obj.SideData.Time,obj.SideData.INT,'r-','LineWidth',1);
            plot(obj.SidePlot,obj.SideData.AllTime,obj.SideData.AllINT,'b.');
            xlabel(obj.SidePlot,'Time (minutes)');
            ylabel(obj.SidePlot,'Intensity');
            hold(obj.SidePlot,'off');
        end
        
        %changes the single tracker plot to m/z vs time
        function plotMZ(obj)
            obj.Type='MZ';
            cla(obj.SidePlot,'reset')
            hold(obj.SidePlot,'on')
            switch obj.Parameters.param.mzTransformation
                case 1 %sqrt
                    mzLim=obj.Parameters.param.mzTolerance/sqrt(obj.Parameters.param.mzAnchor);
                    mzLim=2*mzLim*sqrt(mean(obj.SideData.MZ))+mzLim^2;
                case 2 %none
                    mzLim=obj.Parameters.param.mzTolerance;
            end
            plot(obj.SidePlot,obj.SideData.Time,obj.SideData.MZ,'r-','LineWidth',1);
            hold (obj.SidePlot,'on');
            plot(obj.SidePlot,obj.SideData.Time,obj.SideData.MZ+mzLim,'color',[0.7 0.7 0.7],'LineWidth',1);
            plot(obj.SidePlot,obj.SideData.Time,obj.SideData.MZ-mzLim,'color',[0.7 0.7 0.7],'LineWidth',1);
            plot(obj.SidePlot,obj.SideData.AllTime,obj.SideData.AllMZ,'b.');
            axes(obj.SidePlot)
            set_nice_axis;
            xlabel(obj.SidePlot,'Time (minutes)');
            ylabel(obj.SidePlot,'m/z');
            hold(obj.SidePlot,'off');
        end
        
        %plots the data of a new sample in mainplot, called by selecting a
        %single sample in the samplelist
        function NewSample(obj)
            cla(obj.MainPlot)
            cla(obj.SidePlot)
            SampleName=obj.SampleList.Samples{obj.SampleList.CurrentSample};
            FullSample=obj.SampleList.SamplePath{obj.SampleList.CurrentSample};
            
            PicFile=fullfile(obj.SampleList.ProjectPath,'pic',[SampleName '.pic']);
            if exist(PicFile,'file')==2
                ProcessedParam=load(PicFile,'-mat','param');
                obj.Parameters.param=ProcessedParam.param;
                obj.Parameters.refresh
            end
                
            obj.rawdata=LoadRawDataV3(FullSample,obj.SampleList.ProjectPath);
            if strcmp(obj.rawdata.info.unit,'seconds')
                obj.time=60;
            else
                obj.time=1;
            end
            obj.TimeMargin=5*mean(diff(obj.rawdata.time_axis))/obj.time;
            threshold=prctile(obj.rawdata.intensity_values,99);
            threshold_data=thresholdRawData(obj.rawdata,threshold);
            plotRawData2(obj.MainPlot,threshold_data,'Minutes',obj.time);
            xlabel(obj.MainPlot,'Time (minutes)');
            ylabel(obj.MainPlot,'m/z');
            obj.VisibleTracker_Handle=[];
        end
        
        %loads samples
        function LoadSamples(obj)
            FileChooser(obj.SampleList,' *.CDF;*.XML;*.MZDATA;*.MZXML;*.MAN;*.MZML')
        end
        
        function LoadFiles(obj)
            set(obj.SampleList.ListBox,'String',obj.SampleList.Samples)
            notify(obj,'Samples')
            obj.SampleList.CurrentSample=1;
            obj.NewSample;
        end
        
        %sends selected sample to tracking
        function ProcessSelected(obj)
            fileindex=obj.SampleList.MultiSample;
            files=obj.SampleList.SamplePath(fileindex);
            tracking(files,obj)
        end
        
        %send all loaded samples to tracking
        function ProcessAll(obj)
            tracking(obj.SampleList.SamplePath,obj)
        end
        
        %verifies output and sends data to external function
        function tracking(files,obj)
            
            if isdir(obj.SampleList.ProjectPath)==0
                obj.SampleList.ProjectPath=uigetdir;
            end
            
            if isdir([obj.SampleList.ProjectPath,'/pic'])==0
                mkdir(obj.SampleList.ProjectPath,'pic');
            end
            
            if iscell(files)
                iSamp=1:numel(files);
                for N=1:numel(files)
                    [~, SampleName]=fileparts(files{N});
                    PicFile=fullfile(obj.SampleList.ProjectPath,'pic',[SampleName '.pic']);
                    if exist(PicFile,'file')==2
                        ProcessedParam=load(PicFile,'-mat','param');
                        isEq=ParamCmp(obj.Parameters.param,ProcessedParam.param);
                        if isEq==1
                            iSamp(N)=0;
                        end
                    end
                end
                files(iSamp==0)=[];
            end
            
            %external function for tracking samples and saving data
            TrackSamples(files,obj.SampleList.ProjectPath,obj.Parameters.param)
            notify(obj,'ProjectUpdate')
            if isempty(obj.SampleList.CurrentSample)
                obj.SampleList.CurrentSample=1;
            end
            CurrentPIC=fullfile(obj.SampleList.ProjectPath,'pic',[obj.SampleList.Samples{obj.SampleList.CurrentSample} '.pic']);
            
            if exist(CurrentPIC,'file')
                Tracker=load(CurrentPIC,'-mat');
                obj.tracker_data=Tracker.trackerData;
                obj.summary=Tracker.trackerSummary;
                obj.rawdata=LoadRawDataV3(obj.SampleList.SamplePath(obj.SampleList.CurrentSample));
                obj.MaxTracker=max(obj.tracker_data(:,1));
                obj.Visible=obj.rawdata;
                hold(obj.MainPlot,'on')
                
                for N=1:obj.MaxTracker
                    tracker=obj.tracker_data(:,1)==N;
                    mz=mean(obj.Visible.mass_values(obj.tracker_data(tracker,2)));
                    timevalues=obj.Visible.time_axis(obj.tracker_data(tracker,3))/obj.time;
                    obj.VisibleTracker_Handle(N)=plot(obj.MainPlot,[min(timevalues) max(timevalues)],[mz mz],'r-','LineWidth', 1);
                    set(obj.VisibleTracker_Handle(N),'ButtonDownFcn', @(src,evt)obj.MarkTracker(N));
                end
                set(obj.CurrentTracker,'string','1')
                obj.MarkTracker(1)
            end
        end
    end
end