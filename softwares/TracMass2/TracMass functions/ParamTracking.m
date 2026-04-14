classdef ParamTracking < handle
    %ParamDelaunayClustering - A class for holding paramters in GUI apps
    %   Takes care of various...
    
    %by: Magnus Åberg and Erik Tengstrand
    
    properties ( SetAccess = public )
        minLength=5;
        minIntensity=9;
        mzTolerance=0.0050;
        mzAnchor=400;
        mzTransformation=1;
        rawData_threshold=0;
        mzRange=[0 inf];
        timeRange=[0 inf];
    end
    
    properties ( SetAccess = private )
    end
    
    properties ( Constant = true )
    end
    
    events
        ParamChange
    end
    
    methods
        function obj = ParamTracking( a )

            
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
            
            % a can have more fields than obj but must have all that obj
            % has.
            assert( isempty( setdiff( fn, fieldnames( a ) ) ) )
            
            for i = 1 : numel( fn )
                obj.( fn{ i } ) = a.( fn{ i } );
            end
            notify( obj, 'ParamChange' )
        end
        
        function set.minLength( obj, val )
            val = validateValueAsPosScalar( val );
            obj.minLength = val;
            notify( obj, 'ParamChange' )
        end
        
        function set.minIntensity( obj, val )
            val = validateValueAsPosScalar( val );
            obj.minIntensity = val;
            notify( obj, 'ParamChange' )
        end
        
        function set.mzTolerance( obj, val )
            val = validateValueAsPosScalar( val );
            obj.mzTolerance = val;
            notify( obj, 'ParamChange' )
        end
     
        function set.mzAnchor( obj, val )
            val = validateValueAsPosScalar( val );
            obj.mzAnchor = val;
            notify( obj, 'ParamChange' )
        end        
        
        function set.mzTransformation( obj, val )
            val = validateValueAsPosScalar( val );
            obj.mzTransformation = val;
            notify( obj, 'ParamChange' )
        end
        
        function set.rawData_threshold( obj, val )
            val = validateValueAsPosScalar( val );
            obj.rawData_threshold = val;
            notify( obj, 'ParamChange' )
        end
        
        function set.mzRange( obj, val )
            obj.mzRange = val;
            notify( obj, 'ParamChange' )
        end
        
        function set.timeRange( obj, val )
            obj.timeRange = val;
            notify( obj, 'ParamChange' )
        end
        
        function s = getEditableAsStruct( obj )
            s.minLength = obj.minLength;
            s.minIntensity = obj.minIntensity;
            s.mzTolerance = obj.mzTolerance;
            s.mzAnchor = obj.mzAnchor;
            s.mzTransformation = obj.mzTransformation;
            s.rawData_threshold = obj.rawData_threshold;
            s.mzRange = obj.mzRange;
            s.timeRange = obj.timeRange;
        end
        
        function s = getAsStruct( obj )
            warning( 'off', 'MATLAB:structOnObject' )
            s = struct( obj );
            warning( 'on', 'MATLAB:structOnObject' )
        end
    end
end
