classdef ParamPeakdetection < handle
    %ParamDelaunayClustering - A class for holding paramters in GUI apps
    %   Takes care of various...
    
    %by: Magnus Åberg and Erik Tengstrand
    
    properties ( SetAccess = public )
        zafSigma=2;
        zafWidth=3.5;
        zaf2Sigma=2;
        zaf2Width=3.5;
        gaussSigma=2;
        gaussWidth=3.5;
        nSignalToNoise=4;
        stdFiltWidth=6;
        dt=-1;
        f=[];
    end
    
    properties ( SetAccess = private )
    end
    
    properties ( Constant = true )
    end
    
    events
        ParamChange
    end
    
    methods
        function obj = ParamPeakdetection( a )

            
            if nargin == 1,
                return
            end

            
%             if isa( a, 'PeakDetectionZAF2Param') || isa( a, 'struct' )
%                 setAll( obj, a );
%                 return
%             end
        end
        
        function setAll( obj, a )
            fn = fieldnames( obj );
            %fn = fn(1:9);
            
            % a can have more fields than obj but must have all that obj
            % has.
            assert( isempty( setdiff( fn, fieldnames( a ) ) ) )
            
            for i = 1 : numel( fn )
                obj.( fn{ i } ) = a.( fn{ i } );
            end
            notify( obj, 'ParamChange' )
        end
        
        
        function set.zafSigma( obj, val )
            val = validateValueAsPosScalar( val );
            obj.zafSigma = val;
            notify( obj, 'ParamChange' )
        end
        
        function set.zafWidth( obj, val )
            val = validateValueAsPosScalar( val );
            obj.zafWidth = val;
            notify( obj, 'ParamChange' )
        end
     
        function set.zaf2Sigma( obj, val )
            val = validateValueAsPosScalar( val );
            obj.zaf2Sigma = val;
            notify( obj, 'ParamChange' )
        end        
        
        function set.zaf2Width( obj, val )
            val = validateValueAsPosScalar( val );
            obj.zaf2Width = val;
            notify( obj, 'ParamChange' )
        end
        
        function set.gaussSigma( obj, val )
            val = validateValueAsPosScalar( val );
            obj.gaussSigma = val;
            if obj.dt>0
            if obj.dt/obj.gaussWidth>obj.gaussSigma
                obj.gaussSigma=obj.dt/obj.gaussWidth*1.01;
            end
            obj.f=CalibrateStandardFilter(obj);
            end
            notify( obj, 'ParamChange' )
        end
        
        function set.gaussWidth( obj, val )
            val = validateValueAsPosScalar( val );
            obj.gaussWidth = val;
            notify( obj, 'ParamChange' )
            obj.f=CalibrateStandardFilter(obj);
        end
        
        function set.nSignalToNoise( obj, val )
            val = validateValueAsPosScalar( val );
            obj.nSignalToNoise = val;
            notify( obj, 'ParamChange' )
        end
        
        function set.stdFiltWidth( obj, val )
            val = validateValueAsPosScalar( val );
            obj.stdFiltWidth = val;
            notify( obj, 'ParamChange' )
            obj.f=CalibrateStandardFilter(obj);
        end
        
        %only the field below will be visible for the user.
        function s = getEditableAsStruct( obj )
            s.zafSigma = obj.zafSigma;
            %s.zafWidth = obj.zafWidth;
            s.zaf2Sigma = obj.zaf2Sigma;
            %s.zaf2Width = obj.zaf2Width;
            s.gaussSigma = obj.gaussSigma;
            %s.gaussWidth = obj.gaussWidth;
            s.nSignalToNoise = obj.nSignalToNoise;
            s.stdFiltWidth = obj.stdFiltWidth;
        end
        
        function s = getAsStruct( obj )
            warning( 'off', 'MATLAB:structOnObject' )
            s = struct( obj );
            warning( 'on', 'MATLAB:structOnObject' )
        end
        
        
    end
end
