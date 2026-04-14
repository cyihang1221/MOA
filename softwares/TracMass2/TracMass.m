classdef TracMass < handle
    
    %by: Erik Tengstrand

    properties
        tracker
        detection
        alignment
        ChromView
        
        Tab_Handle
        ChromUpdate=0
    end
    
    
    methods
        
        function obj=TracMass
            splash_handle=SplashScreen('TracMass2!','splashTracMass.png');
            
            Main_Handle=figure('MenuBar','none','Toolbar','figure','Name','TracMass2','Numbertitle','off', 'visible','off');
            obj.Tab_Handle=uiextras.TabPanel('Parent',Main_Handle,'Callback',@(src,evt)obj.tabchange(evt));
            P=get(Main_Handle,'Position');
            set(Main_Handle,'Position',[P(1)-100 P(2)-100 P(3)+200 P(4)+100]);
            
            %creates a problem with the alignment panel
            %set(obj.Tab_Handle,'Callback',@(src,evt)obj.PlotFirst(evt))
            
            obj.ChromView=TM_ChromView(obj.Tab_Handle);
            obj.tracker=TM_tracker(obj.Tab_Handle);
            set(obj.tracker.MainPlot,'Visible','off')
            set(obj.tracker.SidePlot,'Visible','off')
            obj.detection=TM_peakdetection(obj.Tab_Handle);
            set(obj.detection.MainPlot,'Visible','off')
            obj.alignment=TM_alignment(obj.Tab_Handle);
            set(obj.alignment.Cluster1.plothandle,'Visible','off')
            set(obj.alignment.Warp.UpperPlot,'Visible','off')
            set(obj.alignment.Warp.LowerPlot,'Visible','off')
            set(obj.alignment.Cluster2.plothandle,'Visible','off')
            set(obj.alignment.GFHT.UpperPlot,'Visible','off')
            set(obj.alignment.GFHT.MiddlePlot,'Visible','off')
            set(obj.alignment.GFHT.LowerPlot,'Visible','off')
            obj.Tab_Handle.TabNames = {'Chrom' 'Tracking' 'Detection' 'Alignment'};
            obj.Tab_Handle.SelectedChild = 1;
            set(Main_Handle,'Visible','on')
            
            addlistener(obj.tracker,'ProjectUpdate',@(src,evt)obj.ProjectUpdate(src));
            addlistener(obj.detection,'ProjectUpdate',@(src,evt)obj.ProjectUpdate(src));
            addlistener(obj.alignment,'ProjectUpdate',@(src,evt)obj.ProjectUpdate(src));
            addlistener(obj.ChromView,'ProjectUpdate',@(src,evt)obj.ProjectUpdate(src));
            addlistener(obj.ChromView,'Samples',@(src,evt)obj.ChromSamples(src));
            addlistener(obj.tracker,'Samples',@(src,evt)obj.TrackerSamples(src));
            
            delete(splash_handle)
            figure(Main_Handle)
         end
        
        function ProjectUpdate(obj,source)
            if ischar(source.SampleList.ProjectPath)
                Path=source.SampleList.ProjectPath;
                
                %The updating is made as separate functions for clarity
                obj.UpdateViewerAndTracker(Path)
                obj.UpdatePeakdetection(Path)
                obj.UpdateAlignment(Path)
                CreateInfoFile(obj.ChromView);
            end
        end
        
        function tabchange(obj,evt)
            switch evt.PreviousChild
                case 1
                    ChildrenVisibility(obj.ChromView.UpperPlot,'off')
                    ChildrenVisibility(obj.ChromView.LowerPlot,'off')
                case 2
                    ChildrenVisibility(obj.tracker.MainPlot,'off')
                    ChildrenVisibility(obj.tracker.SidePlot,'off')
                case 3
                    ChildrenVisibility(obj.detection.MainPlot,'off')
                case 4
                    ChildrenVisibility(obj.alignment.Cluster1.plothandle,'off')
                    ChildrenVisibility(obj.alignment.Warp.UpperPlot,'off')
                    ChildrenVisibility(obj.alignment.Warp.LowerPlot,'off')
                    ChildrenVisibility(obj.alignment.Cluster2.plothandle,'off')
                    ChildrenVisibility(obj.alignment.GFHT.UpperPlot,'off')
                    ChildrenVisibility(obj.alignment.GFHT.MiddlePlot,'off')
                    ChildrenVisibility(obj.alignment.GFHT.LowerPlot,'off')
            end
            
            switch evt.SelectedChild
                case 1
                    ChildrenVisibility(obj.ChromView.UpperPlot,'on')
                    ChildrenVisibility(obj.ChromView.LowerPlot,'on')
                    if obj.ChromUpdate==1
                        obj.ChromView.PlotAll;
                    end
                case 2
                    ChildrenVisibility(obj.tracker.MainPlot,'on')
                    ChildrenVisibility(obj.tracker.SidePlot,'on')
                case 3
                    ChildrenVisibility(obj.detection.MainPlot,'on')
                case 4
                    switch get(obj.alignment.tabhandle,'SelectedChild')
                        case 1
                            ChildrenVisibility(obj.alignment.Cluster1.plothandle,'on')
                        case 2
                            ChildrenVisibility(obj.alignment.Warp.UpperPlot,'on')
                            ChildrenVisibility(obj.alignment.Warp.LowerPlot,'on')
                        case 3
                            ChildrenVisibility(obj.alignment.Cluster2.plothandle,'on')
                        case 4
                            ChildrenVisibility(obj.alignment.GFHT.UpperPlot,'on')
                            ChildrenVisibility(obj.alignment.GFHT.MiddlePlot,'on')
                            ChildrenVisibility(obj.alignment.GFHT.LowerPlot,'on')
                    end
            end
        end
        
        
        function UpdateViewerAndTracker(obj,Path)
            obj.ChromView.SampleList.ProjectPath=Path;
            obj.tracker.SampleList.ProjectPath=Path;
            
            if exist([Path filesep 'ProjectInfo.txt'],'file')==2
                fid = fopen( [Path filesep 'ProjectInfo.txt'], 'rt' );
                c = char( fread( fid, inf, '*uchar' )' );
                S = regexp(c,'Samples:(?<Samples>.*?)Outliers:','names');
                S.Samples(S.Samples=='\' | S.Samples=='/')=filesep;
                N = regexp(S.Samples,'(?<name>[^\n]*)','names');
                
                for n=1:numel(N)
                    [~,name,~]=fileparts(N(n).name);
                    obj.tracker.SampleList.Samples{n}=name;
                    obj.tracker.SampleList.SamplePath{n}=N(n).name;
                end
                if numel(N)>0
                    obj.ChromView.SampleList.Samples=obj.tracker.SampleList.Samples;
                    obj.ChromView.SampleList.SamplePath=obj.tracker.SampleList.SamplePath;
                    set(obj.tracker.SampleList.ListBox,'String',obj.tracker.SampleList.Samples)
                    set(obj.ChromView.SampleList.ListBox,'String',obj.ChromView.SampleList.Samples)
                    obj.ChromView.SampleList.SamplePath=obj.tracker.SampleList.SamplePath;
                    obj.ChromView.BPC=[];
                    obj.ChromView.TIC=[];
                end
                
                S = regexp(c,'Outliers:(?<Samples>.*)','names');
                S.Samples(S.Samples=='\' | S.Samples=='/')=filesep;
                N = regexp(S.Samples,'(?<name>[^\n]*)','names');
                for n=1:numel(N)
                    [~,name,~]=fileparts(N(n).name);
                    obj.ChromView.Outliers.Samples{n}=name;
                    obj.ChromView.Outliers.SamplePath{n}=N(n).name;
                end
                if numel(N)>0
                    set(obj.ChromView.Outliers.ListBox,'String',obj.ChromView.Outliers.Samples)
                    obj.ChromUpdate=1;
                end
            end
            
            %if the tracker has no samples in the samplelist, it will
            %search the project folder for a folder named raw for samples.
            if numel(obj.tracker.SampleList.Samples)==0 && numel(obj.ChromView.SampleList.Samples)==0
                try
                    path=fullfile(obj.tracker.SampleList.ProjectPath, 'raw');
                    files=dir(path);
                    for N=1:numel(files)
                        [~,name,ext]=fileparts(files(N).name);
                        if strcmpi(ext,'.cdf') || strcmpi(ext,'.mzxml') || strcmpi(ext,'.mzdata') || strcmpi(ext,'.xml') ||  strcmpi(ext,'.mzml') || strcmpi(ext,'.man') 
                            obj.tracker.SampleList.Samples{end+1}=name;
                            obj.tracker.SampleList.SamplePath{end+1}=fullfile(path,[name ext]);
                        end
                    end
                    obj.ChromView.SampleList.Samples=obj.tracker.SampleList.Samples;
                    obj.ChromView.SampleList.SamplePath=obj.tracker.SampleList.SamplePath;
                    set(obj.tracker.SampleList.ListBox,'String',obj.tracker.SampleList.Samples)
                    set(obj.ChromView.SampleList.ListBox,'String',obj.ChromView.SampleList.Samples)
                    obj.ChromView.SampleList.SamplePath=obj.tracker.SampleList.SamplePath;
                    obj.ChromView.BPC=[];
                    obj.ChromView.TIC=[];
                end
            end
            if numel(obj.tracker.SampleList.Samples)==0 && numel(obj.ChromView.SampleList.Samples)==0
                try
                    path=fullfile(obj.tracker.SampleList.ProjectPath, 'raw-dat');
                    files=dir(path);
                    for N=1:numel(files)
                        [~,name,ext]=fileparts(files(N).name);
                        if strcmpi(ext,'.dat')
                            obj.tracker.SampleList.Samples{end+1}=name;
                            obj.tracker.SampleList.SamplePath{end+1}=fullfile(path,[name ext]);
                        end
                    end
                    obj.ChromView.SampleList.Samples=obj.tracker.SampleList.Samples;
                    set(obj.tracker.SampleList.ListBox,'String',obj.tracker.SampleList.Samples)
                    set(obj.ChromView.SampleList.ListBox,'String',obj.ChromView.SampleList.Samples)
                    obj.ChromView.SampleList.SamplePath=obj.tracker.SampleList.SamplePath;
                    obj.ChromView.BPC=[];
                    obj.ChromView.TIC=[];
                end
            end
        end
        
        function UpdatePeakdetection(obj,Path)
            obj.detection.SampleList.ProjectPath=Path;
            %creating list of tracked samples
            files=dir([obj.detection.SampleList.ProjectPath filesep 'pic']);
            obj.detection.SampleList.Samples=[];
            obj.detection.SampleList.SamplePath=[];
            for N=1:numel(files)
                [~,~,ext]=fileparts(files(N).name);
                if strcmpi(ext,'.pic')
                    picfile=fullfile(obj.detection.SampleList.ProjectPath, 'pic', files(N).name);
                    [~,name,~]=fileparts(picfile);
                    obj.detection.SampleList.Samples{end+1}=name;
                    obj.detection.SampleList.SamplePath{end+1}=picfile;
                end
            end
            set(obj.detection.SampleList.ListBox,'String',obj.detection.SampleList.Samples)
        end
        
        function UpdateAlignment(obj,Path)
            obj.alignment.SampleList.ProjectPath=Path;
            obj.alignment.Database.peakList.time=0;
            cla(obj.alignment.Cluster1.plothandle)
            %creating list of samples after peak detection
            files=dir([obj.alignment.SampleList.ProjectPath filesep 'peak']);
            obj.alignment.SampleList.Samples=[];
            obj.alignment.SampleList.SamplePath=[];
            for N=1:numel(files)
                [~,~,ext]=fileparts(files(N).name);
                if strcmpi(ext,'.peak')
                    peakfile=fullfile(obj.alignment.SampleList.ProjectPath, 'peak', files(N).name);
                    [~,name,~]=fileparts(peakfile);
                    obj.alignment.SampleList.Samples{end+1}=name;
                    obj.alignment.SampleList.SamplePath{end+1}=peakfile;
                end
            end
            set(obj.alignment.SampleList.ListBox,'String',obj.alignment.SampleList.Samples)
            
            CC=get(obj.alignment.Cluster1.plothandle,'children');
            if numel(CC)==0 && numel(obj.alignment.SampleList.SamplePath)>0
                peaks=load(obj.alignment.SampleList.SamplePath{1},'-mat');
                plot(obj.alignment.Cluster1.plothandle,peaks.time/peaks.TimeUnit,peaks.mass,'.','color',[0.5 0.5 0.5])
            end
        end
        
        %removes samples from the tracker when they are removed in
        %chromatogram viewer
        function ChromSamples(obj,src)
            set(obj.tracker.SampleList.ListBox,'Value',[])
            obj.tracker.SampleList.Samples=src.SampleList.Samples;
            obj.tracker.SampleList.SamplePath=src.SampleList.SamplePath;
            set(obj.tracker.SampleList.ListBox,'String',obj.tracker.SampleList.Samples);
            CreateInfoFile(obj.ChromView);
        end
        
        function TrackerSamples(obj,src)
            set(obj.ChromView.SampleList.ListBox,'Value',[])
            obj.ChromView.SampleList.Samples=src.SampleList.Samples;
            obj.ChromView.SampleList.SamplePath=src.SampleList.SamplePath;
            set(obj.ChromView.SampleList.ListBox,'String',obj.ChromView.SampleList.Samples);
            obj.ChromView.TIC=[];
            obj.ChromView.BPC=[];
            obj.ChromView.Outliers.Samples=[];
            obj.ChromView.Outliers.MultiSample=[];
            set(obj.ChromView.Outliers.ListBox,'String',[]);
            CreateInfoFile(obj.ChromView);
            obj.ChromUpdate=1;
        end
    end
end


