classdef ClusterPanel < handle
    
    %arguments: parent,parameters, ('Cluster1'/'Cluster2')
    %Cluster1/Cluster2 refers to which peak ID the class will use.
    
    %BY: Erik Tengstrand
    
    properties
        plothandle
        parameters
        Database
        startbutton
        NPurePeaks=0
        EstimatePeaks=100;
        ProcessVisBtn
        EstimateBtn
        ValidateBtn
        parentobj
        SampleBtn
    end
    
    events
        needDatabase
        Finished
    end
    
    
    methods
        
        function obj=ClusterPanel(parent,parameters,Cluster,Database,parentobj)
            
            obj.parentobj=parentobj;
            obj.Database=Database;
            VBox=uiextras.VBox('Parent',double(parent),'Spacing',5,'Padding',5);
            HBox=uiextras.HBox('Parent',double(VBox),'Spacing',5,'Padding',5);
            
            obj.plothandle=axes('Parent',double(VBox),'box','on');
            ylabel( obj.plothandle, 'm/z' )
            xlabel( obj.plothandle, 'Time (minutes)')
            
            set(VBox,'Sizes',[120 -1])
            obj.parameters=ParamPanel(parameters,'Parent',double(HBox),'Title','Parameters');
            BBox=uiextras.VBox('Parent',double(HBox));
            obj.startbutton=uicontrol('Parent',double(BBox),'Style','PushButton','String','Start','enable','off','Callback',@(src,evt)obj.Start(Cluster));
            obj.ProcessVisBtn=uicontrol('Parent',double(BBox),'Style','PushButton','String','Process Visible','enable','off','Callback',@(src,evt)obj.ProcessVisible(Cluster));
            obj.EstimateBtn=uicontrol('Parent',double(BBox),'Style','PushButton','String','Estimate parameters','enable','off','Callback',@(src,evt)obj.Estimate(Cluster));
            obj.ValidateBtn=uicontrol('Parent',double(BBox),'Style','PushButton','String','Validate parameters','enable','off','Callback',@(src,evt)obj.Validate(Cluster));
            obj.SampleBtn=uicontrol('Parent',double(BBox),'Style','PushButton','String','Identify samples','enable','off','Callback',@(src,evt)obj.Sample(Cluster));
            set(obj.SampleBtn,'enable','off')
            
        end
        
        function Start(obj,Cluster)
            %checks that the database has been made, otherwise it calls
            %the alignment class to make a database.
            if numel(obj.Database.peakList.time)<2
                notify(obj,'needDatabase')
            end
            cla(obj.plothandle)
                        
            dim = size( obj.Database.peakList.time );
            
            %to allow backtracking after warping.
            if strcmp(Cluster,'Cluster1')
                Time=obj.Database.peakList.time;
            else
                Time=obj.Database.peakList.warpedtime;
            end
            
            x = Time*60/ (obj.parameters.param.deltaTime) + ( rand( dim ) -.5 )*1e-3;
            y = obj.Database.peakList.mass / (obj.parameters.param.deltaMass) + ( rand( dim ) -.5 )*1e-3;
            obj.Database.peakList.gid = delaunay_align2( x, y );
            
            PL.time=Time;
            PL.mass=obj.Database.peakList.mass;
            PL.gid=obj.Database.peakList.gid;
            PL.sample=obj.Database.peakList.sample;
            
            axes(obj.plothandle);
            cla(obj.plothandle);
            hold(obj.plothandle,'on');
            nClust = numel(unique(obj.Database.peakList.gid));
            disp(' ')
            disp(sprintf('%i clusters',nClust))
            obj.NPurePeaks=numel(getPurePeaks(PL));
            disp(sprintf('%i pure clusters',obj.NPurePeaks))
            
            plotPeakAlignment(PL);
            title( obj.plothandle, sprintf( 'Number of pure clusters: %i',obj.NPurePeaks))
            
            %to allow backtracking after the second clustering the
            %results are stored separtely.
            if strcmp(Cluster,'Cluster1')
                obj.Database.Cluster1ID=obj.Database.peakList.gid;
            end
            if strcmp(Cluster,'Cluster2')
                obj.Database.Cluster2ID=obj.Database.peakList.gid;
            end
            
            notify(obj,'Finished')
            ylabel( obj.plothandle, 'm/z' )
            xlabel( obj.plothandle, 'Time (minutes)')
            set(obj.SampleBtn,'enable','on')
        end
        
        function Sample(obj,Cluster)
            if strcmp(Cluster,'Cluster1')
                Time1=obj.Database.peakList.time;
            else
                Time1=obj.Database.peakList.warpedtime;
            end
            Mass=obj.Database.peakList.mass;
            xlim=get(obj.plothandle,'Xlim');
            ylim=get(obj.plothandle,'Ylim');
            TimeLower=xlim(1);
            TimeHigher=xlim(2);
            MassLower=ylim(1);
            MassHigher=ylim(2);
            inds=true(size(Time1));
            inds(Time1<TimeLower)=false;
            inds(Time1>TimeHigher)=false;
            inds(Mass<MassLower)=false;
            inds(Mass>MassHigher)=false;
            samples=obj.Database.peakList.sample(inds);
            usamp=unique(samples);
            set(obj.parentobj.SampleList.ListBox,'Value',usamp)
        end
        
        function ProcessVisible(obj,Cluster)
            %checks that the database has been made, otherwise it calls
            %the alignment class to make a database.
            if numel(obj.Database.peakList.time)<2
                notify(obj,'needDatabase')
            end
            
            xlim=get(obj.plothandle,'Xlim');
            ylim=get(obj.plothandle,'Ylim');
            TimeLower=xlim(1);
            TimeHigher=xlim(2);
            MassLower=ylim(1);
            MassHigher=ylim(2);
            cla(obj.plothandle)
            
            %to allow backtracking after warping.
            if strcmp(Cluster,'Cluster1')
                Time1=obj.Database.peakList.time;
            else
                Time1=obj.Database.peakList.warpedtime;
            end
            Mass=obj.Database.peakList.mass;
            
            inds=true(size(Time1));
            inds(Time1<TimeLower)=false;
            inds(Time1>TimeHigher)=false;
            inds(Mass<MassLower)=false;
            inds(Mass>MassHigher)=false;
            Mass=Mass(inds);
            Time=Time1(inds);
            
            x = Time*60/ (obj.parameters.param.deltaTime) + ( rand( size(Time) ) -.5 )*1e-3;
            y = Mass / (obj.parameters.param.deltaMass) + ( rand( size(Time) ) -.5 )*1e-3;
            Tcid = delaunay_align2( x, y );
            PL.time=Time;
            PL.mass=Mass;
            PL.gid=Tcid;
            PL.sample=obj.Database.peakList.sample(inds);
            
            axes(obj.plothandle);
            hold(obj.plothandle,'on');
            nClust = numel(unique(Tcid));
            disp(sprintf('%i clusters',nClust))
            obj.NPurePeaks=numel(getPurePeaks(PL));
            disp(sprintf('%i pure clusters',obj.NPurePeaks))
            disp(' ')
            peaks=load(obj.parentobj.SampleList.SamplePath{1},'-mat');
            plot(obj.plothandle,peaks.time/peaks.TimeUnit,peaks.mass,'.','color',[0.7 0.7 0.7])
            plotPeakAlignment(PL);
            set(obj.plothandle,'Xlim',xlim,'Ylim',ylim)
            title( obj.plothandle, sprintf( 'Number of pure clusters: %i',obj.NPurePeaks))
            
            ylabel( obj.plothandle, 'm/z' )
            xlabel( obj.plothandle, 'Time (minutes)')
            set(obj.SampleBtn,'enable','on')
        end
        
        function Estimate(obj,Cluster)
            %checks that the database has been made, otherwise it calls
            %the alignment class to make a database.
            if numel(obj.Database.peakList.time)<2
                notify(obj,'needDatabase')
            end
            
            int=obj.Database.peakList.intensity;
            samp=obj.Database.peakList.sample;
            usamp=obj.Database.sample.id;
            peakInds=zeros(size(int));
            
            for N=1:numel(usamp)
                I=usamp(N);
                index=find(samp==I);
                [~,sortedInds]=sort(int(index),1,'descend');
                peakInds(index(sortedInds(1:obj.EstimatePeaks)))=1;
            end
            peakInds=find(peakInds);
            dim = size(peakInds);
            
            if strcmp(Cluster,'Cluster1')
                Time=obj.Database.peakList.time(peakInds);
            else
                Time=obj.Database.peakList.warpedtime(peakInds);
            end
            Mass=obj.Database.peakList.mass(peakInds);
            
            deltaTime=max(obj.Database.peakList.time)*60*0.02;
            deltaMass=0.2;
            
            x = Time*60/ deltaTime + ( rand( dim ) -.5 )*1e-3;
            y = Mass / deltaMass + ( rand( dim ) -.5 )*1e-3;
            CID= delaunay_align2( x, y );
            
            PL.gid=CID;
            PL.sample=samp(peakInds);
            pCID=getPurePeaks(PL);
            
            upCID=unique(pCID);
            DMass=zeros(size(upCID));
            DTime=zeros(size(upCID));
            
            for N=1:numel(upCID)
                inds=CID==upCID(N);
                
                DMass(N)=max(diff(sort(Mass(inds))));
                DTime(N)=max(diff(sort(Time(inds))))*60;
            end
            
            DMass=sort(DMass);
            DTime=sort(DTime);
            PMass=2*max(DMass)+3*std(DMass);
            PTime=max(DTime);
            obj.parameters.param.deltaTime=PTime;
            obj.parameters.param.deltaMass=PMass;
            obj.parameters.refresh
        end
        
        function Validate(obj,Cluster)
            %checks that the database has been made, otherwise it calls
            %the alignment class to make a database.
            ProgressHandle=waitbar(0,'Estimating parameters','CreateCancelBtn','setappdata(gcbf,''canceling'',1)');
            setappdata(ProgressHandle,'canceling',0)
            if numel(obj.Database.peakList.time)<2
                notify(obj,'needDatabase')
            end
            
            if strcmp(Cluster,'Cluster1')
                Time=obj.Database.peakList.time;
            else
                Time=obj.Database.peakList.warpedtime;
            end
            PL.sample=obj.Database.peakList.sample;
            dim = size( obj.Database.peakList.time );
            
            PT=[0.95 1.05 1 1 1];
            PM=[1 1 0.8 1.2 1];
            
            pureclusters=zeros(5,1);
            for N=1:5
                if getappdata(ProgressHandle,'canceling')
                    break
                end
                x = Time*60/ (obj.parameters.param.deltaTime*PT(N)) + ( rand( dim ) -.5 )*1e-3;
                y = obj.Database.peakList.mass / (obj.parameters.param.deltaMass*PM(N)) + ( rand( dim ) -.5 )*1e-3;
                CID = delaunay_align2( x, y );
                PL.gid=CID;
                pureclusters(N)=numel(getPurePeaks(PL));
                x = Time*60/ obj.parameters.param.deltaTime + ( rand( dim ) -.5 )*1e-3;
                y = obj.Database.peakList.mass / obj.parameters.param.deltaMass + ( rand( dim ) -.5 )*1e-3;
                CID = delaunay_align2( x, y );
                PL.gid=CID;
                pureclusters(5)=numel(getPurePeaks(PL));
                waitbar(0.2*N,ProgressHandle);
            end
            pureclusters(5)=pureclusters(5)+3;
            
            %high time
            if pureclusters(2)>(pureclusters(5)) && pureclusters(2)>pureclusters(1)
                disp('Increase deltaTime')
            end
            
            %low time
            if pureclusters(1)>(pureclusters(5)) && pureclusters(1)>pureclusters(2)
                disp('Decrease deltaTime')
            end
            
            %low mass
            if pureclusters(3)>(pureclusters(5)) && pureclusters(3)>pureclusters(4)
                disp('Decrease deltaMass')
            end
            
            %high mass
            if pureclusters(4)>(pureclusters(5)) && pureclusters(4)>pureclusters(3)
                disp('Increase deltaMass')
            end
            
            if pureclusters(5)==max(pureclusters)
                disp('Good parameters')
            end
            disp(' ')
            delete(ProgressHandle)
        end
    end
end