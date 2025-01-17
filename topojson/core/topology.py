import pprint
import copy
import numpy as np
import itertools
from .hashmap import Hashmap
from ..ops import np_array_from_arcs
from ..ops import dequantize
from ..ops import quantize
from ..ops import simplify
from ..ops import delta_encoding
from ..utils import TopoOptions
from ..utils import serialize_as_svg
from ..utils import serialize_as_json
from ..utils import serialize_as_geojson


class Topology(Hashmap):
    """
    Returns a TopoJSON topology for the specified geometric object. TopoJSON is an 
    extension of GeoJSON providing multiple approaches to compress the geographical 
    input data. These options include simplifying the linestrings or quantizing the 
    coordinates but foremost the computation of a topology.

    Parameters
    ----------
    data : _any_ geometric type
        Geometric data that should be converted into TopoJSON 
    topology : boolean
        Specifiy if the topology should be computed for deriving the TopoJSON. 
        Default is True.
    prequantize : boolean, int
        If the prequantization parameter is specified, the input geometry is 
        quantized prior to computing the topology, the returned topology is 
        quantized, and its arcs are delta-encoded. Quantization is recommended to 
        improve the quality of the topology if the input geometry is messy (i.e., 
        small floating point error means that adjacent boundaries do not have 
        identical values); typical values are powers of ten, such as `1e4`, `1e5` or 
        `1e6`. Default is `True` (which correspond to a quantize factor of `1e6`).
    topoquantize : boolean or int
        If the topoquantization parameter is specified, the input geometry is quantized 
        after the topology is constructed. If the topology is already quantized this 
        will be resolved first before the topoquantization is applied. See for more 
        details the `prequantize` parameter. Default is `False`.
    presimplify : boolean, float
        Apply presimplify to remove unnecessary points from linestrings before the 
        topology is constructed. This will simplify the input geometries. 
        Default is `False`.
    toposimplify : boolean, float 
        Apply toposimplify to remove unnecessary points from arcs after the topology 
        is constructed. This will simplify the constructed arcs without altering the 
        topological relations. Sensible values for coordinates stored in degrees are 
        in the range of `0.0001` to `10`. Defaults to False.
    shared_coords : boolean
        Sets the strategy to detect junctions. When set to `True` a path is 
        considered shared when all coordinates appear in both paths 
        (`coords-connected`). When set to `False` a path is considered shared when 
        coordinates are the same path (`path-connected`). The path-connected strategy 
        is more 'correct', but slower. Default is `False`.
    prevent_oversimplify: boolean
        If this setting is set to `True`, the simplification is slower, but the 
        likelihood of producing valid geometries is higher as it prevents 
        oversimplification. Simplification happens on paths separately, so this 
        setting is especially relevant for rings with no partial shared paths. This 
        is also known as a topology-preserving variant of simplification. 
        Default is `True`.        
    simplify_with : str
        Sets the package to use for simplifying (both pre- and toposimplify). Choose 
        between `shapely` or `simplification`. Shapely adopts solely Douglas-Peucker 
        and simplification both Douglas-Peucker and Visvalingam-Whyatt. The pacakge 
        simplification is known to be quicker than shapely. 
        Default is `shapely`.
    simplify_algorithm : str
        Choose between `dp` and `vw`, for Douglas-Peucker or Visvalingam-Whyatt 
        respectively. `vw` will only be selected if `simplify_with` is set to 
        `simplification`. Default is `dp`, since it still "produces the most accurate 
        generalization" (Chi & Cheung, 2006).
    winding_order : str
        Determines the winding order of the features in the output geometry. Choose 
        between `CW_CCW` for clockwise orientation for outer rings and counter-
        clockwise for interior rings. Or `CCW_CW` for counter-clockwise for outer 
        rings and clockwise for interior rings. Default is `CW_CCW`.
    """

    def __init__(
        self,
        data,
        topology=True,
        prequantize=True,
        topoquantize=False,
        presimplify=False,
        toposimplify=False,
        shared_coords=False,
        prevent_oversimplify=True,
        simplify_with="shapely",
        simplify_algorithm="dp",
        winding_order="CW_CCW",
    ):

        options = TopoOptions(locals())
        # execute previous steps
        super().__init__(data, options)

        # execute main function of Topology
        self.output = self._topo(self.output)

    def __repr__(self):
        return "Topology(\n{}\n)".format(pprint.pformat(self.output))

    @property
    def __geo_interface__(self):
        topo_object = copy.deepcopy(self.output)
        return serialize_as_geojson(topo_object, validate=False, lyr_idx=0)

    def to_dict(self, options=False):
        """
        Convert the Topology to a dictionary.

        Parameters
        ----------
        options : boolean
            If `True`, the options also will be included. 
            Default is `False`
        """
        topo_object = copy.deepcopy(self.output)
        topo_object = self._resolve_coords(topo_object)
        if options:
            topo_object["options"] = vars(self.options)
        return topo_object

    def to_svg(self, separate=False, include_junctions=False):
        """
        Display the arcs and junctions as SVG.

        Parameters
        ----------
        separate : boolean
            If `True`, each of the arcs will be displayed separately. 
            Default is `False`
        include_junctions : boolean
            If `True`, the detected junctions will be displayed as well. 
            Default is `False`
        """
        serialize_as_svg(self.output, separate, include_junctions)

    def to_json(self, fp=None, options=False, pretty=False, indent=4, maxlinelength=88):
        """
        Convert the Topology to a JSON object.

        Parameters
        ----------
        fp : str
            If set, writes the object to a file on drive.
            Default is `None`
        options : boolean
            If `True`, the options also will be included. 
            Default is `False`
        pretty : boolean
            If `True`, the JSON object will be 'pretty', depending on the `ident` and
            `maxlinelength` options 
            Default is `False`
        indent : int
            If `pretty=True`, declares the indentation of the objects.
            Default is `4`.
        maxlinelinelength : int
            If `pretty=True`, declares the maximum length of each line.
            Default is `88`.
        """
        topo_object = copy.deepcopy(self.output)
        topo_object = self._resolve_coords(topo_object)
        if options is True:
            topo_object["options"] = vars(self.options)
        return serialize_as_json(
            topo_object, fp, pretty=pretty, indent=indent, maxlinelength=maxlinelength
        )

    def to_geojson(
        self,
        fp=None,
        pretty=False,
        indent=4,
        maxlinelength=88,
        validate=False,
        objectname="data",
    ):
        """
        Convert the Topology to a GeoJSON object. Remember that this will destroy the
        computed Topology. 

        Parameters
        ----------
        fp : str
            If set, writes the object to a file on drive.
            Default is `None`
        options : boolean
            If `True`, the options also will be included. 
            Default is `False`
        pretty : boolean
            If `True`, the JSON object will be 'pretty', depending on the `ident` and
            `maxlinelength` options 
            Default is `False`
        indent : int
            If `pretty=True`, declares the indentation of the objects.
            Default is `4`
        maxlinelinelength : int
            If `pretty=True`, declares the maximum length of each line.
            Default is `88`
        valide : boolean
            Set to `True` to only return valid geometries objects.
            Default is `False`
        objectname : str
            The name of the object within the Topology to convert to GeoJSON.
            Default is `data` 
        """
        topo_object = copy.deepcopy(self.output)
        topo_object = self._resolve_coords(topo_object)
        fc = serialize_as_geojson(topo_object, validate=validate, objectname=objectname)
        return serialize_as_json(
            fc, fp, pretty=pretty, indent=indent, maxlinelength=maxlinelength
        )

    def to_gdf(self):
        """
        Convert the Topology to a GeoDataFrame. Remember that this will destroy the
        computed Topology. 

        Note: This function use the TopoJSON driver within Fiona to parse the Topology
        to a GeoDataFrame. If data is missing (eg. Fiona cannot parse nested 
        geometrycollections) you can trying using the `.to_geojson()` function prior 
        creating the GeoDataFrame. 
        """
        from ..utils import serialize_as_geodataframe

        topo_object = copy.deepcopy(self.output)
        topo_object = self._resolve_coords(topo_object)
        return serialize_as_geodataframe(topo_object)

    def to_alt(
        self,
        mesh=True,
        color=None,
        tooltip=True,
        projection="identity",
        objectname="data",
    ):
        """
        Display as Altair visualization.

        Parameters
        ----------
        mesh : boolean
            If `True`, render arcs only (mesh object). If `False` render as geoshape. 
            Default is `True`
        color : str
            Assign an property attribute to be used for color encoding. Remember that
            most of the time the wanted attribute is nested within properties. Moreover,
            specific type declaration is required. Eg `color='properties.name:N'`. 
            Default is `None`
        tooltip : boolean
            Option to include or exclude tooltips on geoshape objects
            Default is `True`.
        projection : str
            Defines the projection of the visualization. Defaults to a non-geographic,
            Cartesian projection (known by Altair as `identity`).
        objectname : str
            The name of the object within the Topology to display.
            Default is `data` 
        """
        from ..utils import serialize_as_altair

        topo_object = copy.deepcopy(self.output)
        topo_object = self._resolve_coords(topo_object)
        return serialize_as_altair(
            topo_object, mesh, color, tooltip, projection, objectname
        )

    def to_widget(
        self,
        slider_toposimplify={"min": 0, "max": 10, "step": 0.01, "value": 0.01},
        slider_topoquantize={"min": 1, "max": 6, "step": 1, "value": 1e5, "base": 10},
    ):
        """
        Create an interactive widget based on Altair. The widget includes sliders to 
        interactively change the `toposimplify` and `topoquantize` settings.

        Parameters
        ----------
        slider_toposimplify : dict
            The dict should contain the following keys: `min`, `max`, `step`, `value`
        slider_topoquantize : dict
            The dict should contain the following keys: `min`, `max`, `value`, `base`
        """

        from ..utils import serialize_as_ipywidgets

        return serialize_as_ipywidgets(
            topo_object=self,
            toposimplify=slider_toposimplify,
            topoquantize=slider_topoquantize,
        )

    def topoquantize(self, quant_factor, inplace=False):
        """
        Quantization is recommended to improve the quality of the topology if the 
        input geometry is messy (i.e., small floating point error means that 
        adjacent boundaries do not have identical values); typical values are powers 
        of ten, such as `1e4`, `1e5` or  `1e6`.

        Parameters
        ----------
        quant_factor : float
            tolerance parameter
        inplace : bool, optional
            If `True`, do operation inplace and return `None`. Default is `False`.

        Returns
        -------
        object or None
            Quantized coordinates and delta-encoded arcs or `None` if `inplace` 
            is `True`. 
        """
        result = copy.deepcopy(self)
        arcs = result.output["arcs"]

        if not arcs:
            return result
        # dequantize if quantization is applied
        if "transform" in result.output.keys():
            np_arcs = np_array_from_arcs(arcs)

            transform = result.output["transform"]
            scale = transform["scale"]
            translate = transform["translate"]

            np_arcs = dequantize(np_arcs, scale, translate)
            l_arcs = []
            for ls in np_arcs:
                l_arcs.append(ls[~np.isnan(ls)[:, 0]].tolist())
            arcs = l_arcs

        arcs_qnt, transform = quantize(arcs, result.output["bbox"], quant_factor)

        result.output["arcs"] = delta_encoding(arcs_qnt)
        result.output["transform"] = transform
        result.options.topoquantize = quant_factor

        if inplace:
            # update into self
            self = result
        else:
            return result

    def toposimplify(self, epsilon, inplace=False, _input_as="array"):
        """
        Apply toposimplify to remove unnecessary points from arcs after the topology 
        is constructed. This will simplify the constructed arcs without altering the 
        topological relations. Sensible values for coordinates stored in degrees are 
        in the range of `0.0001` to `10`.

        Parameters
        ----------
        epsilon : float
            tolerance parameter.
        inplace : bool, optional
            If `True`, do operation inplace and return `None`. Default is `False`.
        _input_as : str, optional
            Do not use. Internal used parameter. It can be `linestring` or `array`.
            Default is `array`.

        Returns
        -------
        object or None
            Returns the Topology object with the simplified linestrings or `None` if
            `inplace` is `True`. 
        """
        result = copy.deepcopy(self)

        arcs = result.output["arcs"]
        if arcs:
            np_arcs = np_array_from_arcs(arcs)

            # dequantize if quantization is applied
            if "transform" in result.output.keys():

                transform = result.output["transform"]
                scale = transform["scale"]
                translate = transform["translate"]

                np_arcs = dequantize(np_arcs, scale, translate)

            result.output["arcs"] = simplify(
                np_arcs,
                epsilon,
                algorithm=result.options.simplify_algorithm,
                package=result.options.simplify_with,
                input_as=_input_as,
                prevent_oversimplify=result.options.prevent_oversimplify,
            )

        # quantize aqain if quantization was applied
        if "transform" in result.output.keys():
            if result.options.topoquantize > 0:
                # set default if not specifically given in the options
                if type(result.options.topoquantize) == bool:
                    quant_factor = 1e6
                else:
                    quant_factor = result.options.topoquantize
            elif result.options.prequantize > 0:
                # set default if not specifically given in the options
                if type(result.options.prequantize) == bool:
                    quant_factor = 1e6
                else:
                    quant_factor = result.options.prequantize

            result.output["arcs"], transform = quantize(
                result.output["arcs"], result.output["bbox"], quant_factor
            )

            result.output["coordinates"], transform = quantize(
                result.output["coordinates"], result.output["bbox"], quant_factor
            )

            result.output["arcs"] = delta_encoding(result.output["arcs"])
            result.output["transform"] = transform
        if inplace:
            # update into self
            self.output["arcs"] = result.output["arcs"]
            if "transform" in result.output.keys():
                self.output["transform"] = result.output["transform"]
            # self.output["arcs"] = result.output["arcs"]
            # self.output["transform"] = result.output["transform"]
        else:
            return result

    def _resolve_coords(self, data):
        geoms = data["objects"]["data"]["geometries"]
        for idx, feat in enumerate(geoms):
            if feat["type"] in ["Point", "MultiPoint"]:

                lofl = feat["coordinates"]
                repeat = 1 if feat["type"] == "Point" else 2

                for _ in range(repeat):
                    lofl = list(itertools.chain(*lofl))

                for idx, val in enumerate(lofl):
                    coord = data["coordinates"][val]
                    lofl[idx] = [int(coord.xy[0][0]), int(coord.xy[1][0])]

                feat["coordinates"] = lofl[0] if len(lofl) == 1 else lofl
                feat.pop("reset_coords", None)
        data.pop("coordinates", None)
        return data

    def _topo(self, data):
        self.output["arcs"] = data["linestrings"]
        del data["linestrings"]

        # apply delta-encoding if prequantization is applied
        if self.options.prequantize > 0:
            self.output["arcs"] = delta_encoding(self.output["arcs"])
        else:
            for idx, ls in enumerate(self.output["arcs"]):
                self.output["arcs"][idx] = np.array(ls).tolist()

        # toposimplify linestrings if required
        if self.options.toposimplify > 0:
            # set default if not specifically given in the options
            if type(self.options.toposimplify) == bool:
                simplify_factor = 0.0001
            else:
                simplify_factor = self.options.toposimplify

            self.toposimplify(epsilon=simplify_factor, _input_as="array", inplace=True)

        return self.output
