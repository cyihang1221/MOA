classdef TM_ChromView < handle
    
    %arguments: parent
    %plots the Total Ion Chromatograms (TIC) orc Base Peak Chromatograms
    %(BPC) of the dataset. BPC is default.
    
    %by: Erik Tengstrand
    
    properties
        SampleList
        Outliers
        UpperPlot
        LowerPlot
        PlotMode=1
        TIC
        BPC
        TimeAxis
        PlotHandle
        LowerType=1
        LowerColor=lines(14)
        timeunit=1;
    end
    
    events
        ProjectUpdate
        Samples
        Finished
    end
    
    methods
        function obj=TM_ChromView(parent)
            
            HBoxFlex=uiextras.HBoxFlex('Parent',double(parent),'Spacing',5,'Padding',5);
            
            %leftbox: samplelist and buttons
            LeftBox=uiextras.VBox('Parent',double(HBoxFlex),'Spacing',5,'Padding',5);
            obj.SampleList=TM_samplelist(LeftBox); 
            obj.Outliers=TM_samplelist(LeftBox,'Outliers');
            uicontrol('Parent',double(LeftBox),'Style','PushButton','String','Set Project Folder','Callback',@(src,evt)obj.SetProjectDir());
            uicontrol('Parent',double(LeftBox),'Style','PushButton','String','Load Samples','Callback',@(src,evt)obj.LoadSamples());
            uicontrol('Parent',double(LeftBox),'Style','PushButton','String','Remove Samples','Callback',@(src,evt)obj.RemoveSamples());
            uicontrol('Parent',double(LeftBox),'Style','PushButton','String','Return Outliers','Callback',@(src,evt)obj.ReturnOutliers());
            uicontrol('Parent',double(LeftBox),'Style','PushButton','String','Plot BPC','Callback',@(src,evt)obj.PlotBPC());
            uicontrol('Parent',double(LeftBox),'Style','PushButton','String','Plot TIC','Callback',@(src,evt)obj.PlotTIC());
            set(LeftBox,'Sizes',[-2 -1 25 25 25 25 25 25])
            
            %rightbox: plots for all sample and selected samples
            RightBox=uiextras.VBoxFlex('Parent',double(HBoxFlex),'Spacing',5,'Padding',5);
            obj.UpperPlot=axes('Parent',double(RightBox));
            title(obj.UpperPlot,'BPC')
            obj.LowerPlot=axes('Parent',double(RightBox));
            %linkaxes([obj.UpperPlot obj.LowerPlot])
            set(RightBox,'Sizes',[-2 -1])
            set(HBoxFlex,'Sizes',[-1 -3])
            
            %a listener for when samples are selected in the samplelist
            addlistener(obj.SampleList,'Change',@(src,evt)obj.PlotSelected());
            addlistener(obj.Outliers,'Change',@(src,evt)obj.PlotOutliers());
            addlistener(obj.SampleList,'Finished',@(src,evt)obj.LoadFiles());
            
        end
        
        function LoadFiles(obj)
            set(obj.SampleList.ListBox,'String',obj.SampleList.Samples)
            notify(obj,'Samples')
            obj.TIC=[];
            obj.BPC=[];
            set(obj.SampleList.panel,'Title',sprintf('Samples(%i)',numel(obj.SampleList.Samples)))
            obj.PlotAll;
        end
        
        function LoadSamples(obj)
            FileChooser(obj.SampleList,' *.CDF;*.XML;*.MZDATA;*.MZXML;*.MAN;*.MZML');
        end
        
        function SetProjectDir(obj)
            obj.SampleList.ProjectPath=uigetdir;
            notify(obj,'ProjectUpdate')
            if numel(obj.SampleList.Samples)>1
                obj.PlotAll;
            end
        end
        
        %removes currently selected samples from the sample list; it will 
        %not update the lower plot.
        function RemoveSamples(obj)
            %Add to outlierlist
            for N=1:numel(obj.SampleList.MultiSample)
                obj.Outliers.Samples{end+1}=obj.SampleList.Samples{obj.SampleList.MultiSample(N)};
                obj.Outliers.SamplePath{end+1}=obj.SampleList.SamplePath{obj.SampleList.MultiSample(N)};
            end
            set(obj.Outliers.ListBox,'String',obj.Outliers.Samples)
            
            %updates the TICs, BPCs and plothandles
            obj.BPC(obj.SampleList.MultiSample)=[];
            obj.TIC(obj.SampleList.MultiSample)=[];
            obj.TimeAxis(obj.SampleList.MultiSample)=[];
            obj.PlotHandle(obj.SampleList.MultiSample)=[];
            
            %clears the samplelist and current select samples
            MS=obj.SampleList.MultiSample;
            obj.SampleList.MultiSample=[];
            obj.SampleList.Samples(MS)=[];
            obj.SampleList.SamplePath(MS)=[];
            set(obj.SampleList.ListBox,'Value',[])
            set(obj.SampleList.ListBox,'String',obj.SampleList.Samples)
            set(obj.SampleList.panel,'Title',sprintf('Samples(%i)',numel(obj.SampleList.Samples)))
            cla(obj.LowerPlot,'reset')
            notify(obj,'Samples')
            obj.PlotAll;
        end
        
        %returns samples that have been removed
        function ReturnOutliers(obj)
            %returning samples
            for N=1:numel(obj.Outliers.MultiSample)
                obj.SampleList.Samples{end+1}=obj.Outliers.Samples{obj.Outliers.MultiSample(N)};
                obj.SampleList.SamplePath{end+1}=obj.Outliers.SamplePath{obj.Outliers.MultiSample(N)};
            end
            
            [obj.SampleList.Samples order]=sort(obj.SampleList.Samples);
            obj.SampleList.SamplePath=obj.SampleList.SamplePath(order);
            set(obj.SampleList.ListBox,'String',obj.SampleList.Samples)
            
            %updating the outlierlist
            MS=obj.Outliers.MultiSample;
            obj.Outliers.Samples(MS)=[];
            obj.Outliers.SamplePath(MS)=[];
            set(obj.Outliers.ListBox,'Value',[])
            set(obj.Outliers.ListBox,'String',obj.Outliers.Samples)
            obj.Outliers.MultiSample=[];
            set(obj.SampleList.panel,'Title',sprintf('Samples(%i)',numel(obj.SampleList.Samples)))
            obj.PlotAll;
            switch obj.PlotMode
                case 1
                    title(obj.UpperPlot,'BPC')
                case 2
                    title(obj.UpperPlot,'TIC')
            end
            
            notify(obj,'Samples')
        end
        
        function PlotBPC(obj)
            obj.PlotMode=1;
            obj.PlotAll;
            if numel(obj.SampleList.MultiSample)>0
                obj.PlotSelected;
            end
            if numel(obj.SampleList.MultiSample)==0 && numel(obj.Outliers.MultiSample)>0
                obj.PlotOutliers;
            end
            title(obj.UpperPlot,'BPC')
            axis tight
        end
        
        function PlotTIC(obj)
            obj.PlotMode=2;
            obj.PlotAll;
            if numel(obj.SampleList.MultiSample)>0
                obj.PlotSelected;
            end
            if numel(obj.SampleList.MultiSample)==0 && numel(obj.Outliers.MultiSample)>0
                obj.PlotOutliers;
            end
            title(obj.UpperPlot,'TIC')
            axis tight
        end
        
        %plots all chromatograms in the upper plot
        function PlotAll(obj)
            cla(obj.UpperPlot,'reset')
            xlabel(obj.UpperPlot,'Time (minutes)')
            ylabel(obj.UpperPlot,'Intensity')
            hold(obj.UpperPlot,'on')
            if ischar(obj.SampleList.Samples)
                obj.SampleList.Samples={obj.SampleList.Samples};
                obj.SampleList.SamplePath={obj.SampleList.Samples};
            end
            WaitTotal=numel(obj.SampleList.Samples)-numel(obj.BPC);
            if WaitTotal>0;
                ProgressHandle=waitbar(0,'Loading data','CreateCancelBtn','setappdata(gcbf,''canceling'',1)');
                setappdata(ProgressHandle,'canceling',0)
            end
            WaitCurrent=0;
         %   try
            for N=1:numel(obj.SampleList.Samples)
                if WaitTotal>0
                if getappdata(ProgressHandle,'canceling')
                    fprintf('Process canceled: %i samples loaded. Continue by clicking Load Samples and then Save and Exit.\n',WaitCurrent)
                    warndlg( sprintf('Process canceled: %i samples loaded. Continue by clicking Load Samples and then Save and Exit.',WaitCurrent),'Process canceled')
                    break
                end
                end
                %tests if there is chromatogram data avalible
                try
                    K=numel(obj.BPC{N});
                catch
                    K=-1;
                end
                if K<0
                    if exist(obj.SampleList.ProjectPath,'dir')==7
                        rawDatFile=fullfile(obj.SampleList.ProjectPath,'raw-dat',[obj.SampleList.Samples{N} '.mat']);
                    else
                        rawDatFile=[];
                    end
                    if exist( rawDatFile, 'file' ) == 2
                        Bpc=load(rawDatFile,'BPC');
                        Bpc=Bpc.BPC;
                        Tic=load(rawDatFile,'TIC');
                        Tic=Tic.TIC;
                        Time=load(rawDatFile,'time');
                        Time=Time.time;
                        info=load(rawDatFile,'info');
                        info=info.info;
                    else
                    %loads chromatogram data if not avalible
                    Raw=LoadRawDataV3(obj.SampleList.SamplePath{N},obj.SampleList.ProjectPath);
                    Bpc=getBPC(Raw);
                    Tic=getTIC(Raw);
                    Time=Raw.time_axis;
                    info=Raw.info;
                    end
                    %makes the BPC, TIC and TIME the same length
                    maxIndex=max([numel(Time) numel(Bpc) numel(Tic)]);
                    obj.BPC{N}=Bpc(1:maxIndex);
                    obj.TIC{N}=Tic(1:maxIndex);
                    if strcmp(info.unit,'seconds')
                        obj.TimeAxis{N}=Time(1:maxIndex)/60;
                    else
                        obj.TimeAxis{N}=Time(1:maxIndex);
                    end
                    WaitCurrent=WaitCurrent+1;
                end
                % 1=BPC  2=TIC
                switch obj.PlotMode
                    case 1
                        obj.PlotHandle(N)=plot(obj.UpperPlot,obj.TimeAxis{N},obj.BPC{N},'color',[0 0 1],'LineWidth',1);
                    case 2
                        obj.PlotHandle(N)=plot(obj.UpperPlot,obj.TimeAxis{N},obj.TIC{N},'color',[0 0 1],'LineWidth',1);
                end
                %sets callback function for slecting samples in the upper
                %plot
                set(obj.PlotHandle(N),'ButtonDownFcn',@(src,evt)obj.PlotFromMain(src));
                set(obj.PlotHandle(N),'UserData',N);
                if WaitTotal>0;
                    waitbar(WaitCurrent/WaitTotal,ProgressHandle);
                end
            end
          %  catch
           %     disp('Error: process incomplete')
           % end
            if WaitTotal>0;
                delete(ProgressHandle)
            end
            switch obj.PlotMode
                case 1
                    title(obj.UpperPlot,'BPC')
                case 2
                    title(obj.UpperPlot,'TIC')
            end
        end
        
        %plots selected samples in the lower plot
        function PlotSelected(obj)
            if numel(get(obj.PlotHandle,'children'))==0
                obj.PlotAll;
            end
            
            cla(obj.LowerPlot,'reset')
            hold(obj.LowerPlot,'on')
            if numel(obj.SampleList.Samples)==0 || numel(obj.SampleList.MultiSample)==0
                return
            end
            
            %marks all as blue
            for N=1:numel(obj.SampleList.Samples)
                set(obj.PlotHandle(N),'Color',[0 0 1],'LineWidth',1)
            end
            for N=obj.SampleList.MultiSample
                switch obj.PlotMode
                    case 1
                        LowerHandle=plot(obj.LowerPlot,obj.TimeAxis{N},obj.BPC{N});
                    case 2
                        LowerHandle=plot(obj.LowerPlot,obj.TimeAxis{N},obj.TIC{N});
                end
                %marks selected chromatograms green
                set(obj.PlotHandle(N),'Color',[0 0.7 0],'LineWidth',2)
                
                %makes the different chromatograms have different colors
                %and styles
                set(LowerHandle,'Color',obj.LowerColor(obj.LowerType,:))
                obj.LowerType=obj.LowerType+1;
                if obj.LowerType==8
                    obj.LowerType=1;
                end
                    
                set(LowerHandle,'UserData',N)
                set(LowerHandle,'ButtonDownFcn',@(src,evt)obj.RemoveFromLower(src));
            end
            hLeg=legend(obj.LowerPlot,obj.SampleList.Samples{obj.SampleList.MultiSample},'location','NorthEastOutside');
            set(hLeg,'ButtonDownFcn',@(src,evt)obj.PushLegend(src,'Sample'))
            set(hLeg,'Interpreter','none')
            xlabel(obj.LowerPlot,'Time (minutes)')
            ylabel(obj.LowerPlot,'Intensity')
            
            set(obj.Outliers.ListBox,'Value',[])
            obj.Outliers.MultiSample=[];
        end
        
        function PlotOutliers(obj)
            cla(obj.LowerPlot,'reset')
            hold(obj.LowerPlot,'on')
            %marks all as blue
            for N=1:numel(obj.SampleList.Samples)
                set(obj.PlotHandle(N),'Color',[0 0 1],'LineWidth',1)
            end
            %plots selected samples in the lower plot
            for N=obj.Outliers.MultiSample
                if exist(obj.SampleList.ProjectPath,'dir')==7
                    rawDatFile=fullfile(obj.SampleList.ProjectPath,'raw-dat',[obj.Outliers.Samples{N} '.mat']);
                else
                    rawDatFile=[];
                end
                if exist( rawDatFile, 'file' ) == 2
                    OutlierBPC=load(rawDatFile,'BPC');
                    OutlierTIC=load(rawDatFile,'TIC');
                    info=load(rawDatFile,'info');
                    OutlierBPC=OutlierBPC.BPC;
                    OutlierTIC=OutlierTIC.TIC;
                    Time=load(rawDatFile,'time');
                    Time=Time.time;
                    if strcmp(info.info.unit,'seconds')
                        Time=Time/60;
                    end
                else
                    Raw=LoadRawDataV3(fullfile(obj.Outliers.SamplePath{N}),obj.SampleList.ProjectPath);
                    OutlierBPC=getBPC(Raw);
                    OutlierTIC=getTIC(Raw);
                    Time=Raw.time_axis;
                    if strcmp(raw.info.unit,'seconds')
                        Time=Time/60;
                    end
                end
                
                %makes the BPC, TIC and TIME the same legnth
                maxIndex=max([numel(Time) numel(OutlierBPC) numel(OutlierTIC)]);
                switch obj.PlotMode
                    case 1
                        LowerHandle=plot(obj.LowerPlot,Time(1:maxIndex),OutlierBPC(1:maxIndex));
                    case 2
                        LowerHandle=plot(obj.LowerPlot,Time(1:maxIndex),OutlierTIC(1:maxIndex));
                end
                
                %makes the different chromatograms have different colors
                %and styles
                set(LowerHandle,'Color',obj.LowerColor(obj.LowerType,:))
                obj.LowerType=obj.LowerType+1;
                if obj.LowerType==8
                    obj.LowerType=1;
                end
                
                %marks selected chromatograms green
                set(LowerHandle,'UserData',N)
                set(LowerHandle,'ButtonDownFcn',@(src,evt)obj.RemoveOutlierFromLower(src));
            end
            hLeg=legend(obj.LowerPlot,obj.Outliers.Samples{obj.Outliers.MultiSample},'location','NorthEastOutside');
            set(hLeg,'Interpreter','none')
            set(hLeg,'ButtonDownFcn',@(src,evt)obj.PushLegend(src,'Outlier'))
            xlabel(obj.LowerPlot,'Time (minutes)')
            ylabel(obj.LowerPlot,'Intensity')
            
            set(obj.SampleList.ListBox,'Value',[])
            obj.SampleList.MultiSample=[];
        end
        
        function PushLegend(obj,src,Type)
            c=get(src,'children');
            mask = maskCellByRegexp( get( c, 'Type' ), 'text' );
            cc = c( mask );
            extent = deCell( get( cc ,'Extent' ) );
            extent = reshape( extent, 4, numel( extent ) / 4 )';
            cp = get( src, 'CurrentPoint' );
            ii = find( cp( 1, 2 ) > extent( :, 2 ), 1, 'last' );
            SampleName=get( cc( ii ),'string');
            Plotchildren=get(obj.LowerPlot,'Children');
            for N=1:numel(Plotchildren)
                Name=get(Plotchildren(N),'DisplayName');
                if strcmp(SampleName,Name)
                    if get(Plotchildren(N),'Linewidth')==0.5
                        set(Plotchildren(N),'Linewidth',2)
                        if strcmp(Type,'Sample')
                            ind=find(strcmp(Name,obj.SampleList.Samples));
                            set(double(obj.PlotHandle(ind)),'color',get(Plotchildren(N),'color'))
                        end
                    else
                        set(Plotchildren(N),'Linewidth',0.5)
                        if strcmp(Type,'Sample')
                            ind=find(strcmp(Name,obj.SampleList.Samples));
                            set(double(obj.PlotHandle(ind)),'color',[0 0.7 0],'LineWidth',2)
                        end
                    end
                end
            end
        end
        
        function RemoveOutlierFromLower(obj,src)
            N=get(src,'Userdata');
            obj.Outliers.MultiSample(obj.Outliers.MultiSample==N)=[];
            delete(src)
            if numel(get(obj.LowerPlot,'Children'))==0
                return
            end
            hLeg=legend(obj.LowerPlot,obj.Outliers.Samples{obj.Outliers.MultiSample},'location','NorthEastOutside');
            set(hLeg,'ButtonDownFcn',@(src,evt)obj.PushLegend(src,'Outlier'))
            set(hLeg,'Interpreter','none')
        end
        
        function PlotFromMain(obj,src)
            Nsamp=get(src,'UserData');
            %if the sample is not already selected it is added to the
            %selection
            if sum(Nsamp==obj.SampleList.MultiSample)==0
                obj.SampleList.MultiSample(end+1)=Nsamp;
                set(obj.SampleList.ListBox,'value',obj.SampleList.MultiSample)
            else
                %if the sample is selected, it is removed from selection
                %and the entir selection is plotted again in the lower plot
                obj.SampleList.MultiSample(obj.SampleList.MultiSample==Nsamp)=[];
                set(obj.SampleList.ListBox,'value',obj.SampleList.MultiSample)
            end
            obj.PlotSelected;
        end
        
        %callback to remove a sample from the lower plot by clicking and
        %marking it blue.
        function RemoveFromLower(obj,src)
            N=get(src,'Userdata');
            set(obj.PlotHandle(N),'Color',[0 0 1],'LineWidth',1)
            obj.SampleList.MultiSample(obj.SampleList.MultiSample==N)=[];
            delete(src)
            if numel(get(obj.LowerPlot,'Children'))==0
                return
            end
            hLeg=legend(obj.LowerPlot,obj.SampleList.Samples{obj.SampleList.MultiSample},'location','NorthEastOutside');
            set(hLeg,'ButtonDownFcn',@(src,evt)obj.PushLegend(src,'Samples'))
            set(hLeg,'Interpreter','none')
        end
        
    end
end