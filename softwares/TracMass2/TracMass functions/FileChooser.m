classdef FileChooser < handle
    %Erik Tengstrand
    
    properties
        Samples
        SamplePaths
        OriginalSamples
        OriginalSamplePaths
        SampleList
        
        ListBoxLoad
        Loaded
        LoadedPaths
        ListBoxSamples
        figure_handle
        ProjPath
        FileTypes
        SampleBox
        LastFolder=0;
    end
    
    events
        Finished
    end
    
    methods
        function obj=FileChooser(SampleList,FileTypes)
            
            obj.OriginalSamples=SampleList.Samples;
            obj.Samples=SampleList.Samples;
            obj.SamplePaths=SampleList.SamplePath;
            obj.OriginalSamplePaths=SampleList.SamplePath;
            obj.ProjPath=SampleList.ProjectPath;
            obj.SampleList=SampleList;
            obj.FileTypes=FileTypes;
            
            obj.figure_handle=figure('MenuBar','none','Toolbar','figure','Name','Select files','Numbertitle','off');
            P=get(obj.figure_handle,'Position');
            set(obj.figure_handle,'Position',[P(1)-200 P(4)-200 P(1)+200 P(4)+100]);
            VBox_handle=uiextras.VBox('Parent',double(obj.figure_handle),'Spacing',5,'Padding',5);
            HBoxLists=uiextras.HBox('Parent',double(VBox_handle),'Spacing',5,'Padding',5);
            HBoxBtns=uiextras.HBox('Parent',double(VBox_handle),'Spacing',5,'Padding',5);
            set(VBox_handle,'Sizes',[-1 40])
            
            LoadBox=uiextras.Panel('Parent',double(HBoxLists),'Title','Avalible files');
            obj.ListBoxLoad=uicontrol('Parent',double(LoadBox),'Style','ListBox','String',obj.Loaded,'Max',10000);
            MiddleHBox=uiextras.VBox('Parent',double(HBoxLists),'Spacing',5,'Padding',5);
            obj.SampleBox=uiextras.Panel('Parent',double(HBoxLists),'Title',sprintf('Selected samples (%i)',numel(obj.SampleList.Samples)));
            obj.ListBoxSamples=uicontrol('Parent',double(obj.SampleBox),'Style','ListBox','String',obj.Samples,'Max',10000);
            set(HBoxLists,'Sizes',[-1 100 -1])
            
            uicontrol('Parent',double(HBoxBtns),'Style','PushButton','String','Load folder','Callback',@(src,evt)obj.LoadFolder());
            uicontrol('Parent',double(HBoxBtns),'Style','PushButton','String','Load files','Callback',@(src,evt)obj.LoadFiles());
            uicontrol('Parent',double(HBoxBtns),'Style','PushButton','String','Clear loaded files','Callback',@(src,evt)obj.Clear());
            uiextras.Empty('Parent',double(HBoxBtns));
            uicontrol('Parent',double(HBoxBtns),'Style','PushButton','String','Revert','Callback',@(src,evt)obj.Revert());
            uicontrol('Parent',double(HBoxBtns),'Style','PushButton','String','Exit without saving','Callback',@(src,evt)obj.Exit());
            uicontrol('Parent',double(HBoxBtns),'Style','PushButton','String','Save and exit','Callback',@(src,evt)obj.SaveExit());
            set(HBoxBtns,'Sizes',[100 100 100 -1 100 100 100])
            
            uiextras.Empty('Parent',double(MiddleHBox));
            uicontrol('Parent',double(MiddleHBox),'Style','PushButton','String','>>','Callback',@(src,evt)obj.Select());
            uicontrol('Parent',double(MiddleHBox),'Style','PushButton','String','All >>','Callback',@(src,evt)obj.SelectAll());
            uiextras.Empty('Parent',double(MiddleHBox));
            uicontrol('Parent',double(MiddleHBox),'Style','PushButton','String','<<','Callback',@(src,evt)obj.Remove());
            uicontrol('Parent',double(MiddleHBox),'Style','PushButton','String','<< All','Callback',@(src,evt)obj.RemoveAll());
            uiextras.Empty('Parent',double(MiddleHBox));
            set(MiddleHBox,'Sizes',[-1 25 25 -1 25 25 -1])
        end
        
        function Clear(obj)
            obj.Loaded=[];
            obj.LoadedPaths=[];
            set(obj.ListBoxLoad,'String',obj.Loaded)
        end
        
        function LoadFolder(obj)
            if obj.LastFolder==0
                folder=uigetdir(obj.ProjPath);
            else
                folder=uigetdir(obj.LastFolder);
            end
            obj.LastFolder=folder;
            try
                files=dir(folder);
                for N=1:numel(files)
                    [~,name,ext]=fileparts(files(N).name);
                    ext=lower(ext);
                    CurrentFile=[folder filesep name ext];
                    switch obj.FileTypes
                        case ' *.CDF;*.XML;*.MZDATA;*.MZXML;*.MAN;*.MZML'
                            if ( strcmp(ext,'.cdf') || strcmp(ext,'.xml') || strcmp(ext,'.mzxml') || strcmp(ext,'.mzdata') ) && sum(strcmp(CurrentFile,obj.Loaded))==0 && sum(strcmp(name,obj.Samples))==0
                                obj.LoadedPaths{end+1}=CurrentFile;
                                obj.Loaded{end+1}=name;
                            end
                        case ' *.PIC'
                            if  strcmp(ext,'.pic') && sum(strcmp(CurrentFile,obj.Loaded))==0 && sum(strcmp(name,obj.Samples))==0
                                obj.LoadedPaths{end+1}=CurrentFile;
                                obj.Loaded{end+1}=name;
                            end
                        case ' *.PEAK'
                            if  strcmp(ext,'.peak') && sum(strcmp(CurrentFile,obj.Loaded))==0 && sum(strcmp(name,obj.Samples))==0
                                obj.LoadedPaths{end+1}=CurrentFile;
                                obj.Loaded{end+1}=name;
                            end    
                    end
                end
                set(obj.ListBoxLoad,'String',obj.Loaded)
            end
        end
        
        function LoadFiles(obj)
            if obj.LastFolder==0
                [LSamp LSampPath]=uigetfile([obj.ProjPath filesep obj.FileTypes],'MultiSelect','on');
            else
                [LSamp LSampPath]=uigetfile([obj.LastFolder filesep obj.FileTypes],'MultiSelect','on');
            end
            obj.LastFolder=LSampPath;
            if iscell(LSamp)
                for N=1:numel(LSamp)
                    [~,name,ext]=fileparts(LSamp{N});
                    ext=lower(ext);
                    CurrentFile=[LSampPath name ext];
                    if ( strcmp(ext,'.cdf') || strcmp(ext,'.xml') || strcmp(ext,'.mzxml') || strcmp(ext,'.mzdata') || strcmp(ext,'.dat') ) && sum(strcmp(CurrentFile,obj.LoadedPaths))==0 && sum(strcmp(name,obj.SamplePaths))==0
                        obj.LoadedPaths{end+1}=CurrentFile;
                        obj.Loaded{end+1}=name;
                    end
                end
            end
            if ischar(LSamp)
                [~,name,ext]=fileparts(LSamp);
                ext=lower(ext);
                CurrentFile=[LSampPath name ext];
                if ( strcmp(ext,'.cdf') || strcmp(ext,'.xml') || strcmp(ext,'.mzxml') || strcmp(ext,'.mzdata') || strcmp(ext,'.dat') ) && sum(strcmp(CurrentFile,obj.LoadedPaths))==0 && sum(strcmp(name,obj.SamplePaths))==0
                    obj.LoadedPaths{end+1}=CurrentFile;
                    obj.Loaded{end+1}=name;
                end
            end
            set(obj.ListBoxLoad,'String',obj.Loaded)
        end
        
        function Revert(obj)
            obj.Samples=obj.OriginalSamples;
            obj.SamplePaths=obj.OriginalSamplePaths;
            set(obj.ListBoxSamples,'String',obj.Samples)
        end
        
        function Exit(obj)
            delete(obj.figure_handle)
        end
        
        function SaveExit(obj)
            obj.SampleList.Samples=obj.Samples;
            obj.SampleList.SamplePath=obj.SamplePaths;
            delete(obj.figure_handle)
            notify(obj.SampleList,'Finished')
        end
        
        function Select(obj)
            Selection=get(obj.ListBoxLoad,'Value');
            if numel(Selection)==0
                return
            end
            
            for N=1:numel(Selection)
                obj.Samples{end+1}=obj.Loaded{Selection(N)};
                obj.SamplePaths{end+1}=obj.LoadedPaths{Selection(N)};
            end
            obj.Loaded(Selection)=[];
            obj.LoadedPaths(Selection)=[];
            [obj.Samples order]=unique(obj.Samples');
            obj.SamplePaths=obj.SamplePaths(order);
            set(obj.ListBoxLoad,'String',obj.Loaded)
            set(obj.ListBoxSamples,'String',obj.Samples)
            set(obj.ListBoxLoad,'Value',[])
            set(obj.SampleBox,'Title',sprintf('Selected samples (%i)',numel(obj.Samples)));
        end
        
        function SelectAll(obj)
            if numel(obj.Loaded)==0
                return
            end
            
            for N=1:numel(obj.Loaded)
                obj.Samples{end+1}=obj.Loaded{N};
                obj.SamplePaths{end+1}=obj.LoadedPaths{N};
            end
            obj.Loaded=[];
            obj.LoadedPaths=[];
            [obj.Samples order]=unique(obj.Samples);
            obj.SamplePaths=obj.SamplePaths(order);
            set(obj.ListBoxLoad,'String',obj.Loaded)
            set(obj.ListBoxSamples,'String',obj.Samples)
            set(obj.ListBoxLoad,'Value',[])
            set(obj.SampleBox,'Title',sprintf('Selected samples (%i)',numel(obj.Samples)))
        end
        
        function Remove(obj)
            Selection=get(obj.ListBoxSamples,'Value');
            if numel(Selection)==0
                return
            end
                
            for N=1:numel(Selection)
                obj.Loaded{end+1}=obj.Samples{Selection(N)};
                obj.LoadedPaths{end+1}=obj.SamplePaths{Selection(N)};
            end
            obj.Samples(Selection)=[];
            obj.SamplePaths(Selection)=[];
            set(obj.ListBoxLoad,'String',obj.Loaded)
            set(obj.ListBoxSamples,'String',obj.Samples)
            set(obj.ListBoxSamples,'Value',[])
            set(obj.SampleBox,'Title',sprintf('Selected samples (%i)',numel(obj.Samples)))
        end
        
        function RemoveAll(obj)
            if numel(obj.Samples)==0
                return
            end
            
            for N=1:numel(obj.Samples)
                obj.Loaded{end+1}=obj.Samples{N};
                obj.LoadedPaths{end+1}=obj.SamplePaths{N};
            end
            obj.Samples=[];
            obj.SamplePaths=[];
            set(obj.ListBoxLoad,'String',obj.Loaded)
            set(obj.ListBoxSamples,'String',obj.Samples)
            set(obj.ListBoxSamples,'Value',[])
            set(obj.SampleBox,'Title',sprintf('Selected samples (%i)',numel(obj.Samples)))
        end
    end
end
