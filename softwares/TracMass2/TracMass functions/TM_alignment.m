classdef TM_alignment < handle
    
    %arugment: parent
    %a class for alignment in TracMass
    
    %by: Erik Tengstrand
    
    properties
        SampleList
        Parameters %database parameters
        Database
        tabhandle
        Exportbutton
        Binningbutton
        
        %handles for the alignment methods
        Cluster1
        Warp
        Cluster2
        GFHT
        
        %alignment parameters
        paramWarp
        paramClust1
        paramClust2
        paramHough
    end
    
    events
        ProjectUpdate
        C2Finish
    end
    
    methods
        
        function obj=TM_alignment(parent)
            
            obj.Database.peakList.time=0;
            HBox=uiextras.HBoxFlex('Parent',double(parent),'Spacing',5,'Padding',5);
            LeftBox=uiextras.VBox('Parent',double(HBox),'Spacing',5,'Padding',5);
            obj.SampleList=TM_samplelist(LeftBox);
            RightBox=uiextras.VBox('Parent',double(HBox),'Spacing',5,'Padding',5);
            set(HBox,'Sizes',[-1 -3]);
            
            obj.Parameters.param=ParamDatabase;
            %parameterpanel removed because the parameters for the database
            %buildning are rarely neccessary
            %obj.Parameters=ParamPanel(param,'Parent',LeftBox,'Title','Parameters');
            TM_ui(obj,LeftBox,'alignment');
            uicontrol('Parent',double(LeftBox),'Style','PushButton','String','Load Samples','Callback',@(src,evt)obj.LoadSamples());
            uicontrol('Parent',double(LeftBox),'Style','PushButton','String','Save Alignment','Callback',@(src,evt)obj.SaveAlignment());
            uicontrol('Parent',double(LeftBox),'Style','PushButton','String','Load Alignment','Callback',@(src,evt)obj.LoadAlignment());
            obj.Exportbutton=uicontrol('Parent',double(LeftBox),'Style','PushButton','String','Export with GFHT','enable','off','Callback',@(src,evt)obj.ExportGFHT());
            obj.Binningbutton=uicontrol('Parent',double(LeftBox),'Style','PushButton','String','Export from Cluster 2','enable','off','Callback',@(src,evt)obj.ExportBinning());
            set(LeftBox,'Sizes',[-1 25 25 25 25 25 25 25 25])
            
            obj.tabhandle=uiextras.TabPanel('Parent',double(RightBox),'Callback',@(src,evt)obj.tabchange(evt));
                        
            %cluster1
            obj.paramClust1 = ParamDelaunayClustering;
            obj.paramClust1.deltaMass = 0.01;
            obj.paramClust1.deltaTime = 10;
            obj.Cluster1=ClusterPanel(obj.tabhandle,obj.paramClust1,'Cluster1',obj.Database,obj);
            addlistener(obj.Cluster1,'needDatabase',@(src,evt)obj.BuildDB());
            set(obj.Cluster1.startbutton,'enable','on')
            set(obj.Cluster1.ProcessVisBtn,'enable','on')
            set(obj.Cluster1.EstimateBtn,'enable','on')
            set(obj.Cluster1.ValidateBtn,'enable','on')
            addlistener(obj.Cluster1,'Finished',@(src,evt)obj.Cluster1Finish());
            
            %warping
            obj.paramWarp = ParamPSplineWarping;
            obj.Warp=warppanel(obj.tabhandle,obj.paramWarp,obj.SampleList,obj.Database);
            addlistener(obj.Warp,'Finished',@(src,evt)obj.WarpFinish());
            
            %cluster2
            obj.paramClust2 = ParamDelaunayClustering; %parameters
            obj.paramClust2.deltaMass = 0.01;
            obj.paramClust2.DTChanged=0;
            obj.Cluster2=ClusterPanel(obj.tabhandle,obj.paramClust2,'Cluster2',obj.Database,obj);
            addlistener(obj.Cluster2,'Finished',@(src,evt)obj.Cluster2Finish());
            
            %GFHT
            obj.paramHough = ParamHoughResolution;
            obj.GFHT=TM_HoughPanel(obj.tabhandle,obj.paramHough,obj.Database,obj);
            addlistener(obj.GFHT,'Finished',@(src,evt)obj.GFHTFinish());
            
            
            obj.tabhandle.TabNames = { 'Cluster', 'Warp', 'Cluster #2', 'Hough resolve'};
            set( obj.tabhandle, 'SelectedChild', 1 )
            addlistener(obj.SampleList,'Finished',@(src,evt)obj.LoadFiles());
        end
        
        function tabchange(obj,evt)
            switch evt.PreviousChild
                case 1
                    ChildrenVisibility(obj.Cluster1.plothandle,'off')
                case 2
                    ChildrenVisibility(obj.Warp.UpperPlot,'off')
                    ChildrenVisibility(obj.Warp.LowerPlot,'off')
                case 3
                    ChildrenVisibility(obj.Cluster2.plothandle,'off')
                case 4
                    ChildrenVisibility(obj.GFHT.UpperPlot,'off')
                    ChildrenVisibility(obj.GFHT.MiddlePlot,'off')
                    ChildrenVisibility(obj.GFHT.LowerPlot,'off')
            end
            
            switch evt.SelectedChild
                case 1
                    ChildrenVisibility(obj.Cluster1.plothandle,'on')
                case 2
                    ChildrenVisibility(obj.Warp.UpperPlot,'on')
                    ChildrenVisibility(obj.Warp.LowerPlot,'on')
                case 3
                    ChildrenVisibility(obj.Cluster2.plothandle,'on')
                case 4
                    ChildrenVisibility(obj.GFHT.UpperPlot,'on')
                    ChildrenVisibility(obj.GFHT.MiddlePlot,'on')
                    ChildrenVisibility(obj.GFHT.LowerPlot,'on')
            end
        end
        
        function LoadFiles(obj)
            set(obj.SampleList.ListBox,'String',obj.SampleList.Samples)
        end
        
        function LoadSamples(obj)
            FileChooser(obj.SampleList,'*.PEAK')
        end
        
        function BuildDB(obj)
            disp('Building database')
            obj.Database=TM_database(obj.SampleList,obj.Parameters.param);
            obj.Cluster1.Database=obj.Database;
            obj.Cluster2.Database=obj.Database;
            obj.Warp.Database=obj.Database;
            obj.GFHT.Database=obj.Database;
        end
        
        function Cluster1Finish(obj)
            set(obj.Warp.startbutton,'enable','on')
            cla(obj.Warp.UpperPlot)
            cla(obj.Warp.LowerPlot)
            if obj.Warp.parameters.param.PSplineChanged==0 && obj.Cluster1.NPurePeaks>0;
                obj.Warp.parameters.param.numPSplines=ceil(obj.Cluster1.NPurePeaks/20);
                obj.Warp.parameters.refresh;
                obj.Warp.parameters.param.PSplineChanged=0;
            end
        end
        
        function WarpFinish(obj)
            set(obj.Cluster2.startbutton,'enable','on')
            set(obj.Cluster2.ProcessVisBtn,'enable','on')
            set(obj.Cluster2.EstimateBtn,'enable','on')
            set(obj.Cluster2.ValidateBtn,'enable','on')
            cla(obj.Cluster2.plothandle)
            if obj.Cluster2.parameters.param.DTChanged == 0 && obj.Cluster1.NPurePeaks>0;
                obj.Cluster2.parameters.param.deltaTime=obj.Cluster1.parameters.param.deltaTime * 0.7;
                obj.Cluster2.parameters.param.deltaMass=obj.Cluster1.parameters.param.deltaMass;
                obj.Cluster2.parameters.refresh;
                obj.Cluster2.parameters.param.DTChanged=0;
            end
            peaks=load(obj.SampleList.SamplePath{1},'-mat');
            plot(obj.Cluster2.plothandle,peaks.time/peaks.TimeUnit,peaks.mass,'.','color',[0.5 0.5 0.5])
        end
        
        function Cluster2Finish(obj)
            obj.GFHT.Database=obj.Cluster2.Database;
            obj.GFHT.parameters.param.TimeTolerance=obj.Cluster2.parameters.param.deltaTime;
            obj.GFHT.parameters.refresh;
            cla(obj.GFHT.UpperPlot)
            cla(obj.GFHT.MiddlePlot)
            cla(obj.GFHT.LowerPlot)
            set(obj.GFHT.startbutton,'enable','on')
            set(obj.Binningbutton,'enable','on')
            notify(obj.GFHT,'C2Finish');
        end
        
        function GFHTFinish(obj)
            set(obj.Exportbutton,'enable','on')
        end
        
        function SaveAlignment(obj)
            [filename pathname]=uiputfile('.align','',obj.SampleList.ProjectPath);
            if ischar(filename)
                savedata.data=obj.Database;
                Param.db=obj.Parameters.param;
                Param.c1=obj.Cluster1.parameters.param;
                Param.W=obj.Warp.parameters.param;
                Param.c2=obj.Cluster2.parameters.param;
                Param.H=obj.GFHT.parameters.param;
                savedata.Param=Param;
                savedata.path=obj.SampleList.ProjectPath;
                savefile=fullfile(pathname,filename);
                save(savefile,'savedata','-mat');
            end
        end
        
        
        function LoadAlignment(obj)
            try
                [filename pathname]=uigetfile('.align','',obj.SampleList.ProjectPath);
                loadfile=fullfile(pathname,filename);
                savedata=load(loadfile,'-mat');
                
                Param=savedata.savedata.Param;
                obj.SampleList.ProjectPath=savedata.savedata.path;
                notify(obj,'ProjectUpdate')
                obj.Parameters.param=Param.db;
                obj.Cluster1.parameters.param=Param.c1;
                obj.Cluster1.parameters.refresh;
                obj.Warp.parameters.param=Param.W;
                obj.Warp.parameters.refresh;
                obj.Cluster2.parameters.param=Param.c2;
                obj.Cluster2.parameters.refresh;
                obj.GFHT.parameters.param=Param.H;
                obj.GFHT.parameters.refresh;
                notify(obj.GFHT,'LoadAlignment')
                
                obj.Database=savedata.savedata.data;
                obj.Cluster1.Database=obj.Database;
                obj.Warp.Database=obj.Database;
                obj.Cluster2.Database=obj.Database;
                obj.GFHT.Database=obj.Database;
                if numel(obj.Database.Cluster1ID)>0
                    set(obj.Warp.startbutton,'enable','on')
                    
                    PL.time=obj.Database.peakList.time;
                    PL.mass=obj.Database.peakList.mass;
                    PL.gid=obj.Database.Cluster1ID;
                    PL.sample=obj.Database.peakList.sample;
                    axes(obj.Cluster1.plothandle);
                    plotPeakAlignment(PL);
                end
                if numel(obj.Database.WarpedTime)>0
                    set(obj.Cluster2.startbutton,'enable','on')
                    set(obj.Cluster2.ProcessVisBtn,'enable','on')
                    set(obj.Cluster2.EstimateBtn,'enable','on')
                    set(obj.Cluster2.ValidateBtn,'enable','on')
                    
                    obj.Warp.PlotWarpAll;
                end
                if numel(obj.Database.Cluster2ID)>0
                    set(obj.GFHT.startbutton,'enable','on')
                    set(obj.Binningbutton,'enable','on')
                    
                    PL.time=obj.Database.peakList.warpedtime;
                    PL.mass=obj.Database.peakList.mass;
                    PL.gid=obj.Database.Cluster2ID;
                    PL.sample=obj.Database.peakList.sample;
                    axes(obj.Cluster2.plothandle);
                    plotPeakAlignment(PL);
                    obj.GFHT.PlotCollisions;
                end
                if numel(obj.Database.HoughID)>0
                    set(obj.Exportbutton,'enable','on')
                end
            catch
                errordlg( 'The file is an invalid alignment data file','Loading error');
            end
        end
        
        function ExportGFHT(obj)
            PL=obj.Database.peakList;
            PL.gid=obj.Database.Cluster2ID;
            mask=find(PL.gid~=obj.Database.HoughID);
            nHough=numel(mask);
            PL.gid((end+1):(end+nHough))=obj.Database.HoughID(mask);
            PL.sample((end+1):(end+nHough))=PL.sample(mask);
            PL.intensity((end+1):(end+nHough))=PL.intensity(mask);
            PL.time((end+1):(end+nHough))=PL.time(mask);
            PL.mass((end+1):(end+nHough))=PL.mass(mask);
            obj.binning(PL);
        end
        
        function ExportBinning(obj)
            obj.Database.peakList.gid=obj.Database.Cluster2ID;
            PL=obj.Database.peakList;
            obj.binning(PL);
        end
        
        %takes the highest of the unresolved peaks
        function binning(obj,pl)
            [file path]=uiputfile('*.csv','Export aligned data',obj.SampleList.ProjectPath);
            if file==0
                return
            end
            pl.sampGid=pl.gid+pl.sample/(10^log10(max(obj.Database.sample.id)));
            pl=sortTable(pl,'sampGid');
            pl.binning=zeros(size(pl.gid));
            [counts, indStart, ~]=getCounts2(pl.sampGid);
            toBin=find(counts>1);
            for N=toBin
                pl.intensity(indStart(N)+1)=max(pl.intensity(indStart(N)+1:counts(N)));
                pl.gid(indStart(N)+2:counts(N))=-1;
                pl.binning(indStart(N)+1)=1;
            end
            pl=maskTable(pl,pl.gid~=-1);
            oldPL=obj.Database.peakList;
            obj.Database.peakList=pl;
            try
                tracMassWritePeakSummary([path file],obj.Database,1);
                disp('Export complete')
            end
            obj.Database.peakList=oldPL;
        end
        
    end
end