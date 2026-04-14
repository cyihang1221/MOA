classdef warppanel < handle
    
    %arguments: parent, parameters, samplelist
    %samplelist refers to the samplelist in the parent class
    
    %by: Erik Tengstrand and Magnus Åberg
    
    properties
        UpperPlot
        LowerPlot
        parameters
        Database
        WarpPlot
        samplelist
        startbutton
    end
    
    events
        Finished
    end
    
    
    methods
        
        function obj=warppanel(parent,parameters,samplelist,Database)
            
            obj.Database=Database;
            
            VBox=uiextras.VBox('Parent',double(parent),'Spacing',5,'Padding',5);
            HBox=uiextras.HBox('Parent',double(VBox),'Spacing',5,'Padding',5);
            VBoxFlex=uiextras.VBoxFlex('Parent',double(VBox),'Spacing',5,'Padding',5);
            obj.UpperPlot=axes('Parent',double(VBoxFlex),'box','on');
            xlabel(obj.UpperPlot,'Retention time (minutes)')
            ylabel(obj.UpperPlot,'Peak shift (seconds)')
            obj.LowerPlot=axes('Parent',double(VBoxFlex),'box','on');
            set(VBox,'Sizes',[50 -1])
            obj.parameters=ParamPanel(parameters,'Parent',double(HBox),'Title','Parameters');
            obj.startbutton=uicontrol('Parent',double(HBox),'Style','PushButton','String','Start','enable','off','Callback',@(src,evt)obj.Start());
            
            addlistener(samplelist,'ChangeSample',@(src,evt)obj.PlotWarp());
            obj.samplelist=samplelist;
        end
        
        
        function Start(obj)
            cla(obj.UpperPlot,'reset')
            cla(obj.LowerPlot,'reset')
            xlabel(obj.UpperPlot,'Retention time (minutes)')
            ylabel(obj.UpperPlot,'Peak shift (seconds)')
            xlabel(obj.LowerPlot,'Retention time (minutes)')
            ylabel(obj.LowerPlot,'Peak shift (seconds)')
            obj.Database.peakList.gid=obj.Database.Cluster1ID;
            peakList=obj.Database.peakList;
            gidp = getPurePeaks( obj.Database.peakList );
            
            mask = false( size( obj.Database.peakList.id ) );
            for i = 1 : numel( gidp ),
                mask = mask | obj.Database.Cluster1ID == gidp( i );
            end
            tab = maskTable( obj.Database.peakList, mask );
            
            
            [ X, idSamp, idPeak ] = tabToMatrix( tab, 'sample', 'gid', 'time' );
            x = nanmean( X )'; % ' column vector (avg retention time of each peak)
            [ x, iix ] = sort( x );
            
            % set up parameters and spline bases
            ndx = obj.parameters.param.numPSplines; % number of b-splines
            ndx = min( ndx, numel( idPeak ) );
            if exist( 'nPSpline', 'var' )
                ndx = nPSpline;
            end
            bdeg = 2; % b-spline polynomial basis
            pord = 2; % smoothing penalty order
            Lambda = obj.parameters.param.lambda;
            
            xl = floor( min( tab.time ) );
            xr = ceil( max( tab.time ) );
            obj.Database.bSplineRange = [ xl xr ];
            
            B = bspline( x, xl, xr, ndx, bdeg );
            % fit p-splines for smoothing
            xnice = linspace( xl, xr, 1000 )';
            obj.Database.xNice = xnice;
            Bnice = bspline( xnice, xl, xr, ndx, bdeg );
            obj.Database.BNice = Bnice;
            warpedTime = obj.Database.peakList.time;
            idSamp = unique( tab.sample );

            for kSamp = 1:numel( idSamp ),
                sampleToSmooth = idSamp( kSamp );
                
                mSamp = obj.Database.peakList.sample == sampleToSmooth;
                xWarp = obj.Database.peakList.time( mSamp );
                BWarp = bspline( xWarp, xl, xr, ndx, bdeg );
                
                y = X( kSamp, iix )' - x; % ' column vector of deviations from the mean
                
                softness=abs(PSplines( y, B, pord, 10^-10,0)-PSplines( y, B, pord, 10^10,0))/10;
                L=minimizeGCV( y, B, pord, softness);
                
                [ a, GCV, yhat ] = fitPSplines( y, B, pord, 10^L );
                
                YWarp{ kSamp } = BWarp * a;
                theLambda( kSamp, 1 ) = Lambda;
                theA( kSamp ,: ) = a;
                g( kSamp, 1 ) = GCV;
                warpedTime( mSamp ) = obj.Database.peakList.time( mSamp ) - YWarp{ kSamp };
                
            end
            
            % save results
            obj.Database.WarpedTime=warpedTime;
            obj.Database.theGCV = g;
            obj.Database.coeffs = theA;
            obj.Database.peakList = peakList;
            obj.Database.peakList.warpedtime = warpedTime;
            obj.Database.Time = X( :, iix )';
            obj.Database.meanTime = x;
            
            
            %plot results
            obj.PlotWarpAll;
            
            notify(obj,'Finished')
            
        end
            
        function PlotWarpAll(obj)
            hold( obj.UpperPlot, 'on' )
            obj.WarpPlot = plot( obj.UpperPlot, obj.Database.xNice, obj.Database.BNice * obj.Database.coeffs'*60, '-' );
            xlabel(obj.UpperPlot,'Retention time (minutes)')
            ylabel(obj.UpperPlot,'Peak shift (seconds)')
            set( [ obj.UpperPlot; obj.WarpPlot ], 'ButtonDownFcn', @(src,evt)obj.PushWarpPlot(src));
            for Nwarp=1:numel(obj.WarpPlot)
                set(obj.WarpPlot(Nwarp),'Userdata',obj.Database.sample.id(Nwarp));
            end
        end
        
        function PushWarpPlot(obj,src)
            obj.samplelist.CurrentSample=get(src,'Userdata');
            obj.PlotWarp
        end
        
        function PlotWarp(obj)
            %if the white region is pushed, the plotting will fail
            try
                set(obj.WarpPlot,'Linewidth',0.5)
                current=obj.samplelist.CurrentSample;
                set(obj.samplelist.ListBox,'value',obj.samplelist.CurrentSample);
                set(obj.WarpPlot(current),'Linewidth',1.5)
                cla(obj.LowerPlot)
                xlabel(obj.LowerPlot,'Retention time (minutes)')
                ylabel(obj.LowerPlot,'Peak shift (seconds)')
                Y=obj.Database.BNice * obj.Database.coeffs'*60;
                Y=Y(:,current);
                plot(obj.LowerPlot,obj.Database.xNice,Y);
                hold(obj.LowerPlot,'on')
                plot(obj.LowerPlot,obj.Database.meanTime,(obj.Database.Time(:,current) - obj.Database.meanTime)*60,'.k');
            end
        end
        
    end
end
