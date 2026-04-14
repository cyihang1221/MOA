classdef ParamDatabase < handle
    %ParamDelaunayClustering - A class for holding paramters in GUI apps
    %   Takes care of various...
    
    %by: Magnus Åberg
    
    properties ( SetAccess = public )
        StartTime=0;
        EndTime=Inf;
        MinMZ=0;
        MaxMZ=Inf;
        IntensityThreshold=0;
    end
    
    properties ( SetAccess = private )
    end
    
    properties ( Constant = true )
    end
    
    events
        ParamChange
    end
    
    methods
        function obj = ParamDelaunayClustering( a )

            
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
        
        function set.StartTime( obj, val )
            val = validateValueAsPosScalar( val );
            obj.StartTime= val;
            notify( obj, 'ParamChange' )
        end
        
        function set.EndTime( obj, val )
            val = validateValueAsPosScalar( val );
            obj.EndTime = val;
            notify( obj, 'ParamChange' )
        end
        
        function set.MinMZ( obj, val )
            val = validateValueAsPosScalar( val );
            obj.MinMZ = val;
            notify( obj, 'ParamChange' )
        end
     
        function set.MaxMZ( obj, val )
            val = validateValueAsPosScalar( val );
            obj.MaxMZ = val;
            notify( obj, 'ParamChange' )
        end        
        
       
        function set.IntensityThreshold( obj, val )
            val = validateValueAsPosScalar( val );
            obj.IntensityThreshold = val;
            notify( obj, 'ParamChange' )
        end
    
        function s = getEditableAsStruct( obj )
            s.StartTime = obj.StartTime;
            s.EndTime = obj.EndTime;
            s.MinMZ = obj.MinMZ;
            s.MaxMZ = obj.MaxMZ;
            s.IntensityThreshold = obj.IntensityThreshold;
        end
        
        function s = getAsStruct( obj )
            warning( 'off', 'MATLAB:structOnObject' )
            s = struct( obj );
            warning( 'on', 'MATLAB:structOnObject' )
        end
    end
end
