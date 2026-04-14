classdef PeakDetectionZAF2Param < handle
    %PeakDetectionZAF2Param - A class for holding paramters in GUI apps
    %   Takes care of various...
    
    %by: Magnus Åberg and Erik Tengstrand
    
    properties ( SetAccess = public )
        zafSigma
        zaf2Sigma
        gaussSigma
        nSignalToNoise
        stdFiltWidth
        dt
    end
    
    properties ( SetAccess = private )
        f
    end
    
    properties ( Constant = true )
        zafWidth = 3.5;
        gaussWidth = 3.5;
    end
    
    events
        ParamChange
    end
    
    
    methods
        function obj = PeakDetectionZAF2Param( a )
            obj.zafSigma = 1;
            obj.zaf2Sigma = 1.5;
            obj.gaussSigma = 2;
            obj.nSignalToNoise = 3;
            obj.stdFiltWidth = 4;
            
            obj.dt = [];
            obj.calibrate;
            
            if nargin == 0,
                return
            end
            
            if isa( a, 'PeakDetectionZAF2Param') || isa( a, 'struct' )
                setAll( obj, a );
                return
            end
        end
        
        function setAll( obj, a )
            fn = fieldnames( obj );
            fn = fn(1:5);
            
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
        
        function set.zaf2Sigma( obj, val )
            val = validateValueAsPosScalar( val );
            obj.zaf2Sigma = val;
            notify( obj, 'ParamChange' )
        end
        
        function set.gaussSigma( obj, val )
            val = validateValueAsPosScalar( val );
            obj.gaussSigma = val;
            obj.calibrate;
            notify( obj, 'ParamChange' )
        end
        
        function set.nSignalToNoise( obj, val )
            val = validateValueAsPosScalar( val );
            obj.nSignalToNoise = val;
            notify( obj, 'ParamChange' )
        end
        
        function set.stdFiltWidth( obj, val )
            val = validateValueAsPosScalar( val );
            obj.stdFiltWidth = val;
            obj.calibrate;
            
            notify( obj, 'ParamChange' )
        end
        
        function set.dt( obj, val )
            assert( ( numel( val ) == 1 && val > 0 ) || ...
             numel( val ) == 0)
            obj.dt = val;
            obj.calibrate;
            
            notify( obj, 'ParamChange' )
        end
        
        function s = getEditableAsStruct( obj )
            s.zafSigma = obj.zafSigma;
            s.zaf2Sigma = obj.zaf2Sigma;
            s.gaussSigma = obj.gaussSigma;
            s.nSignalToNoise = obj.nSignalToNoise;
            s.stdFiltWidth = obj.stdFiltWidth;
        end
        
        function s = getAsStruct( obj )
            s = getEditableAsStruct( obj );
            s.zafWidth = obj.zafWidth;
            s.gaussWidth = obj.gaussWidth;
            s.f = obj.f;
        end
        
        function calibrate( obj )
            if ~ isempty( obj.stdFiltWidth ) && ...
                    ~ isempty( obj.gaussSigma ) && ...
                    ~ isempty( obj.gaussWidth ) && ...
                ~ isempty( obj.dt )
                
                gauss = mk_gauss( obj.dt, obj.gaussSigma, obj.gaussWidth );
                obj.f = calibrate_stdFilter( gauss, obj.stdFiltWidth, 1e3 )
            end
        end
    end
end
